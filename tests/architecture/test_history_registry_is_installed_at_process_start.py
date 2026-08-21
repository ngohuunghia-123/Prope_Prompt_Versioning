"""ADR-0038 at the composition roots: both processes install the cache, neither mounts a route.

**Structural, over the source, because neither startup path is reachable
behaviourally.** ``tests/integration/_asgi.py`` calls the application object
directly and runs no lifespan, so a behavioural test would assert nothing about
``prope.app``. The register is ``test_route_table.py``'s, which reads
``_start_publisher`` through ``inspect.getsource`` for the same reason.

The imported-name assertion is the half that carries security weight. What it
refuses is not a typo: it is a **router** reaching a composition root — which
would fail PH-07 — or an ``append`` / ``read`` call reaching one, which would put
a database write inside a lifespan.

The last two tests assert the cache's own contract rather than its composition:
what got installed is the immutable seeded vocabulary, and ``registered_registry``
refuses by name before an install. They live here because the refusal is the other
half of the same decision — a process either holds the vocabulary or does not
exist.
"""

import ast
import inspect
from pathlib import Path
from types import MappingProxyType

import pytest

import prope.app
import prope.worker
from prope.property_history.registry import (
    install_registry,
    registered_registry,
    reset_registry,
)

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope"

#: The whole surface either composition root may take from property-history.
COMPOSITION_IMPORTS = frozenset({"install_registry", "load_action_registry"})

COMPOSITION_ROOTS = (SOURCE_ROOT / "app.py", SOURCE_ROOT / "worker.py")


def _property_history_imports(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("prope.property_history"):
                imported.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("prope.property_history"):
                    imported.add(alias.asname or alias.name)
    return imported


def test_the_asgi_lifespan_loads_and_installs_the_registry() -> None:
    startup = inspect.getsource(prope.app.lifespan)

    assert "load_action_registry(session)" in startup
    assert "install_registry(" in startup
    # Before the publisher, so a process that cannot record a state change never
    # starts one that could produce one.
    assert startup.index("install_registry(") < startup.index("_start_publisher(")


def test_run_worker_loads_and_installs_the_registry() -> None:
    startup = inspect.getsource(prope.worker.run_worker)

    assert "load_action_registry(session)" in startup
    assert "install_registry(" in startup
    assert startup.index("install_registry(") < startup.index("await supervise(")


def test_each_composition_root_imports_exactly_the_two_composition_names() -> None:
    for module in COMPOSITION_ROOTS:
        assert _property_history_imports(module) == COMPOSITION_IMPORTS, (
            f"{module.name} imports something else from prope.property_history. A router here "
            "would fail PH-07; an append() or read() here would put a database write in a "
            "process's startup path."
        )


def test_the_walk_actually_found_an_import_to_check() -> None:
    """Guards the walk against passing because it inspected nothing.

    A refactor that moved the install elsewhere would otherwise leave this file
    green over two empty sets.
    """
    found = sum(len(_property_history_imports(module)) for module in COMPOSITION_ROOTS)
    assert found >= 2, f"the walk found {found} property-history imports across both roots"


def test_the_installed_cache_is_the_immutable_seeded_vocabulary() -> None:
    """What the rig installed is what a process installs: 43 rows, and no way to edit them.

    37 until 2026-08-18; ADR-0061 registered `namespace_access_granted` and
    `namespace_access_revoked` in revision 0026, and ADR-0067 registered
    `usage_profile_changed` in revision 0031 — prompt-registry's event, because the
    axes are prompt-registry's columns. The FK from `history_event` to
    this registry is what makes the seed load-bearing rather than documentation:
    an event written under an unregistered action is refused by the database.
    """
    registry = registered_registry()

    assert len(registry) == 43
    assert isinstance(registry, MappingProxyType)
    with pytest.raises(TypeError):
        registry["injected"] = None  # type: ignore[index]


def test_registered_registry_refuses_by_name_before_any_install() -> None:
    """An empty mapping would page property-history for a composition bug (ADR-0038).

    Restores the rig's installed cache in ``finally`` — this is the one test that
    takes the session-scoped fixture's state away from every test after it.
    """
    installed = registered_registry()
    reset_registry()
    try:
        with pytest.raises(RuntimeError) as excinfo:
            registered_registry()
    finally:
        install_registry(installed)

    message = str(excinfo.value)
    assert "install_registry" in message
    assert "prope.app" in message
    assert "prope.worker.run_worker" in message

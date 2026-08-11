"""``dependencies: []`` as a checked property, not a design intention (D-75).

``docs/modules/property-history.lock.yml`` declares an empty dependency list and
names seven forbidden edges, each of which is individually tempting: resolving a
``target_id`` to a title for a nicer feed, checking a permission before returning
a trail, consulting the decision the trail is recording. A signature review
proves ``read()`` has no actor parameter *today*; this proves the package has
nothing to check *with*, on every run for the remaining nineteen phases — which
is the interval over which the tempting edge actually gets added.

**What this file is NOT.** It is not a claim that no other module may import
property-history. Five of them will, from Phase 7 on, and that direction is the
whole design.

Same shape as ``test_no_sql_interpolation.py``: a discovered file list, a closed
allow-list with its reason in place, and vacuity guards.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "property_history"

#: The only ``prope`` packages this module may import, and why neither is a
#: module dependency. ``prope.db`` is the shared session and metadata seam every
#: module uses and that owns nothing; ``prope.property_history`` is itself.
#: Anything else is an edge out of a module whose lock file declares
#: ``dependencies: []``.
ALLOWED_PROPE_IMPORTS = frozenset({"prope.db", "prope.property_history"})

VIOLATION = (
    "property-history declares `dependencies: []`, and every one of the seven forbidden edges is "
    "individually tempting — resolving a target_id to a title, checking a permission, consulting "
    "the decision it is recording. If this import is genuinely needed the lock file is wrong, and "
    "that is an OQ rather than an allow-list entry."
)


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    """Every module name imported by ``module``, with its line number.

    A relative import resolves to the package itself, which is why it is
    reported as ``prope.property_history`` rather than skipped.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.property_history" if node.level else (node.module or "")
            imported.append((node.lineno, name))
    return imported


def _forbidden_prope_imports(module: Path) -> list[tuple[int, str]]:
    return [
        (line, name)
        for line, name in _imported_modules(module)
        if name.split(".")[0] == "prope"
        and not any(
            name == allowed or name.startswith(f"{allowed}.") for allowed in ALLOWED_PROPE_IMPORTS
        )
    ]


def _package_modules() -> list[Path]:
    modules = sorted(PACKAGE.rglob("*.py"))
    assert modules, f"no modules found under {PACKAGE}; the walk is looking in the wrong place"
    return modules


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_module_imports_a_prope_package_outside_the_allow_list(module: Path) -> None:
    found = _forbidden_prope_imports(module)
    assert not found, f"{module.name}: {found} — {VIOLATION}"


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_fastapi_is_imported_at_no_depth(module: Path) -> None:
    """A-123's *no HTTP route is mounted*, as a test rather than a one-day grep."""
    names = [name for _, name in _imported_modules(module)]
    assert not [name for name in names if name.split(".")[0] == "fastapi"], names


def test_the_shared_observability_module_is_not_imported() -> None:
    """Phase 4 put this module's one counter inside the package for exactly this reason.

    ``src/prope/observability.py`` is not on the allow-list, so this is the
    absence rather than an exception — and stating it separately means a future
    import of it fails with a sentence about *why* rather than only *which*.
    """
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}
    assert "prope.observability" not in imported


def test_the_walk_found_modules_and_imports_to_inspect() -> None:
    """A walk pointed at the wrong directory would otherwise be green."""
    modules = _package_modules()
    assert len(modules) >= 4, modules
    assert sum(len(_imported_modules(module)) for module in modules) >= 10


def test_the_walk_refuses_a_module_that_reaches_another_bounded_context(tmp_path: Path) -> None:
    """The guard is known to have teeth, proven on a file written here.

    Without this, an allow-list check that accidentally matched everything would
    pass on the real package for the same reason it passes on nothing.
    """
    tempting = tmp_path / "activity_feed.py"
    tempting.write_text(
        "from prope.call_ledger.api import router\nfrom prope.db.session import "
        "workspace_transaction\n",
        encoding="utf-8",
    )

    assert _forbidden_prope_imports(tempting) == [(1, "prope.call_ledger.api")]

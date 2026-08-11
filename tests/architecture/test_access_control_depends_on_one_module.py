"""`dependencies: [property-history]` as a checked property, not an intention.

`docs/modules/access-control.lock.yml` declares exactly one module dependency and
names the forbidden edges. The tempting one is specific and it is named in
ADR-0020: reading the subject this module is authorising — a `prompt_property`
row to learn `owner_id`, an `access_level` to decide visibility. Every caller
already holds that row, so the edge buys nothing and costs six cycles.

Same shape as `test_property_history_depends_on_nothing.py`, with one difference:
**FastAPI is permitted here.** This module mounts sixteen routes.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "access_control"

#: `prope.db` is the shared session/metadata seam that owns nothing;
#: `prope.errors` and `prope.session_auth` are shared infrastructure outside every
#: module's package; `prope.dependencies` holds the two FastAPI dependencies every
#: router needs; `prope.observability` is the shared log-field allow-list;
#: `prope.property_history` is the one declared module dependency.
ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        "prope.db",
        "prope.dependencies",
        "prope.errors",
        "prope.observability",
        "prope.property_history",
        "prope.session_auth",
    }
)

VIOLATION = (
    "access-control declares one module dependency. ADR-0020 is the reason: this module may not "
    "read any subject it authorises — callers pass owner_id and access_level from the row they "
    "already read. An import here is one of the six cycles that rule exists to make unnecessary."
)


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.access_control" if node.level else (node.module or "")
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


def test_call_ledger_is_imported_at_no_depth() -> None:
    """ADR-0018 makes call-ledger a sink. An inbound edge is the whole prohibition.

    Stated separately from the allow-list so that the failure names the rule
    rather than only the missing entry. It is also the import that was very nearly
    made: the error envelope lived in `call_ledger/schemas.py` until Phase 7 moved
    it to `prope.errors` (OQ-021), and reaching for it where it used to be is a
    one-line mistake with an architectural consequence.
    """
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}
    assert not [name for name in imported if name.startswith("prope.call_ledger")], sorted(imported)


def test_the_walk_found_modules_and_imports_to_inspect() -> None:
    modules = _package_modules()
    assert len(modules) >= 12, modules
    assert sum(len(_imported_modules(module)) for module in modules) >= 30


def test_the_walk_refuses_a_module_that_reaches_another_bounded_context(tmp_path: Path) -> None:
    """The guard is known to have teeth, proven on a file written here."""
    tempting = tmp_path / "read_the_subject.py"
    tempting.write_text(
        "from prope.prompt_registry.models import prompt_property\n"
        "from prope.db.session import workspace_transaction\n",
        encoding="utf-8",
    )

    assert _forbidden_prope_imports(tempting) == [(1, "prope.prompt_registry.models")]

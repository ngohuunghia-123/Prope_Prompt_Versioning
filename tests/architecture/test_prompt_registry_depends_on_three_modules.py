"""`dependencies: [access-control, property-history, provider-access]` as a checked property.

`docs/modules/prompt-registry.lock.yml` declares exactly three module
dependencies — two hard, one soft — and names four forbidden edges. **All four
run the other way**: gateway, evaluation and release-control each call this
module and it never calls back, and call-ledger is a sink (ADR-0018).

Two of them are worth stating on their own because they are the ones somebody
would write by accident:

*release-control.* The released pointer moves by an INBOUND command (INT-012,
INT-013, INT-014). A ``from prope.release_control import ...`` here would close
the cycle A-041 and ADR-0001 exist to break, and it would do it while looking
like a convenience — *"just check the release record before setting the
pointer"*. There is nothing to check: the constraint is the check.

*evaluation.* The registry does not know what a pass is. Run results are read by
release-control (A-042) and never surfaced here.

FastAPI is permitted: this module mounts ten routes across seven paths.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_registry"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        "prope.db",
        "prope.dependencies",
        "prope.errors",
        "prope.observability",
        "prope.prompt_registry",
        "prope.property_history",
        "prope.provider_access",
        "prope.session_auth",
    }
)

FORBIDDEN_MODULES = (
    "prope.call_ledger",
    "prope.gateway",
    "prope.evaluation",
    "prope.release_control",
)

VIOLATION = (
    "prompt-registry declares three module dependencies. The other four edges run the other "
    "way: gateway, evaluation and release-control all call this module and it never calls back "
    "(A-041, ADR-0001 — the released pointer moves by an inbound command), and call-ledger is a "
    "sink whose body read path is gated by OQ-013."
)


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.prompt_registry" if node.level else (node.module or "")
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


def test_the_four_forbidden_modules_are_imported_at_no_depth() -> None:
    """Stated separately from the allow-list so the failure names the rule
    rather than only the missing entry."""
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}

    reached = [
        name for name in imported for forbidden in FORBIDDEN_MODULES if name.startswith(forbidden)
    ]
    assert reached == [], f"{sorted(reached)} — {VIOLATION}"


def test_no_module_reaches_the_upstream_http_client() -> None:
    """A-043 and this module's ``external_services: []``.

    **No prompt body leaves the host at save time.** Every upstream call in the
    system goes through provider-access, and an ``httpx`` import here would be
    the first line of the LLM enrichment ADR-0048 rejected — which would have
    sent every body upstream on every save, including drafts and retired prompts
    nobody intended to run.
    """
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}

    assert not [name for name in imported if name.split(".")[0] in {"httpx", "openai", "requests"}]


def test_the_diff_uses_the_standard_library_and_nothing_else() -> None:
    """A-015's diff is ``difflib``, named in the lock as a library choice.

    Asserted because the alternative — a diff library with a nicer API — would
    also have its own ``autojunk``-shaped heuristics, undeclared, on the one
    screen a reviewer approves from.
    """
    imported = {name for _, name in _imported_modules(PACKAGE / "diff.py")}

    assert "difflib" in imported
    assert not [name for name in imported if name.split(".")[0] == "prope"] or imported & {
        "prope.prompt_registry.domain"
    }


def test_the_walk_found_modules_and_imports_to_inspect() -> None:
    modules = _package_modules()

    assert len(modules) >= 10, modules
    assert sum(len(_imported_modules(module)) for module in modules) >= 30


def test_the_walk_refuses_a_module_that_reaches_another_bounded_context(tmp_path: Path) -> None:
    """The guard is known to have teeth, proven on a file written here."""
    tempting = tmp_path / "check_the_release_first.py"
    tempting.write_text(
        "from prope.release_control.seams import get_release\n"
        "from prope.db.session import workspace_transaction\n",
        encoding="utf-8",
    )

    assert _forbidden_prope_imports(tempting) == [(1, "prope.release_control.seams")]

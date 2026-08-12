"""`dependencies: [access-control, property-history]` as a checked property.

`docs/modules/provider-access.lock.yml` declares exactly two module dependencies
and names five forbidden edges. Four of them are direction rules — gateway,
evaluation, prompt-registry and release-control all depend on this module and
never the reverse — and the fifth is ADR-0018's sink: call-ledger is not called
from here, because usage is *returned* to whoever dispatched and they submit it.
Writing usage from this module would create a second submitter and put a write
on the response path.

FastAPI is permitted: this module mounts ten routes across six paths.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "provider_access"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        "prope.db",
        "prope.dependencies",
        "prope.errors",
        "prope.observability",
        "prope.property_history",
        "prope.provider_access",
        "prope.session_auth",
    }
)

FORBIDDEN_MODULES = (
    "prope.call_ledger",
    "prope.gateway",
    "prope.evaluation",
    "prope.prompt_registry",
    "prope.release_control",
)

VIOLATION = (
    "provider-access declares two module dependencies. The other five edges run the other way: "
    "gateway, evaluation, prompt-registry and release-control all call this module and it never "
    "calls back, and call-ledger is a sink (ADR-0018) — usage is returned to whoever dispatched "
    "and they submit it."
)


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.provider_access" if node.level else (node.module or "")
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


def test_the_five_forbidden_modules_are_imported_at_no_depth() -> None:
    """Stated separately from the allow-list so the failure names the rule
    rather than only the missing entry."""
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}

    reached = [
        name for name in imported for forbidden in FORBIDDEN_MODULES if name.startswith(forbidden)
    ]
    assert reached == [], f"{sorted(reached)} — {VIOLATION}"


def test_the_openai_sdk_is_never_imported_by_runtime_code() -> None:
    """It is AC-9's oracle and a dev-group dependency. It is deliberately NOT
    the client: A-088's exactly-one-attempt against its default of two retries,
    AC-9's unknown-field pass-through against its typed models, and ADR-0047's
    address pinning against a client that owns its own connection each rule it
    out independently."""
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}

    assert not [name for name in imported if name.split(".")[0] == "openai"], sorted(imported)


def test_httpx_is_the_client_everywhere_an_upstream_call_is_made() -> None:
    """ADR-0047 decides the client, and it is one client rather than a habit."""
    upstream = PACKAGE / "upstream.py"

    assert "httpx" in {name for _, name in _imported_modules(upstream)}


def test_the_walk_found_modules_and_imports_to_inspect() -> None:
    modules = _package_modules()

    assert len(modules) >= 14, modules
    assert sum(len(_imported_modules(module)) for module in modules) >= 40


def test_the_walk_refuses_a_module_that_reaches_another_bounded_context(tmp_path: Path) -> None:
    """The guard is known to have teeth, proven on a file written here."""
    tempting = tmp_path / "submit_the_usage.py"
    tempting.write_text(
        "from prope.call_ledger.seams import enqueue\n"
        "from prope.db.session import workspace_transaction\n",
        encoding="utf-8",
    )

    assert _forbidden_prope_imports(tempting) == [(1, "prope.call_ledger.seams")]

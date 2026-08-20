"""`dependencies: [prompt-registry, evaluation, provider-access, access-control,
call-ledger]`, checked — and one forbidden edge that the module's whole design
turns on.

**release-control is forbidden IN BOTH DIRECTIONS, and that is not a preference.**
The lock's flow originally said the reviewer's report is frozen at submit, which
would have needed a hook inside release-control. Both clauses could not hold, and
the ban won: the freeze now happens on the first card read past `Draft`, made
safe by `uq_readiness_report_version` rather than by a caller. This test is what
keeps the resolution honest — the day somebody adds `from prope.release_control
import ...` to write the report "properly at submit", the constraint that was
argued for stops being a constraint, and nothing else in the suite would notice.

**property-history is forbidden too, and its absence is a decision with a
reason.** A dismissal is recorded in `readiness.dismissal`, on
prompt-observation's A-102 precedent — a dismissed finding is not a state change
on a prompt property. Routing it through history would have widened
`ck_history_action_registry_writing_module_values` for a tenth writing module
nothing reads. The one history event this feature does produce,
`usage_profile_changed`, is prompt-registry's, written by prompt-registry,
because the four axes are columns on `registry.prompt_property`.

**call-ledger is a DIRECTION rather than a module.** ADR-0018 closes the body
read path and the lock forbids the read side by name; `price_probe_usage` is the
write side and is allowed. `test_the_only_call_ledger_symbols_used_are_the_write_side`
is what holds the direction, because the allow-list alone cannot.

**`prope.app_agent` is allowed and is not a ninth module.** It is the shared
runtime prompt-conversion and prompt-search already use — a client, a circuit
breaker and a DSPy runtime, not a bounded context. Lane B reaches it; nothing
else here does, and `tests/security/test_readiness_holds_no_outbound_capability.py`
enumerates exactly which files may.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_readiness"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        # Lane B's runtime. Shared infrastructure, not a bounded context.
        "prope.app_agent",
        "prope.call_ledger",
        "prope.db",
        # The management surface this module mounts on: A-045's error envelope
        # and its closed code vocabulary. Unlike the gateway, these five routes
        # ARE management routes and answer in that shape.
        "prope.dependencies",
        "prope.errors",
        "prope.evaluation",
        "prope.observability",
        # `canonical_prompt` and `prompt_composition` are shared parsers, not
        # modules. Lane A reads block structure and the PLACEHOLDER regex from
        # them ON PURPOSE (A-011, A-078): a second copy of either would be a
        # second definition of what a variable is, and the rule would eventually
        # disagree with what `render` actually substitutes.
        "prope.canonical_prompt",
        "prope.prompt_composition",
        "prope.prompt_readiness",
        "prope.prompt_registry",
        "prope.provider_access",
        "prope.session_auth",
    }
)

FORBIDDEN_MODULES = (
    "prope.release_control",
    "prope.property_history",
    "prope.prompt_search",
    "prope.chat_orchestrator",
    "prope.prompt_observation",
    "prope.prompt_conversion",
)

VIOLATION = (
    "prompt-readiness declares five module dependencies. release-control is forbidden IN BOTH "
    "DIRECTIONS (SR-1) and is the reason the reviewer's report freezes on the card READ rather "
    "than at submit; property-history is forbidden because a dismissal is not a state change on "
    "a prompt property (A-102), and the one history event this feature writes is "
    "prompt-registry's; call-ledger is write-only, because it is a sink (ADR-0018)."
)

#: What may be reached inside `prope.call_ledger`. `seams` carries
#: `price_probe_usage` and `check_spend_ceiling`; `domain` carries `Outcome`,
#: which the probe stamps onto a usage row. Anything else in that package —
#: `repository`, `api`, `reader` — is the ledger doing its own work, and the
#: lock forbids this module a read path into it by name.
ALLOWED_CALL_LEDGER_MODULES = frozenset({"prope.call_ledger.domain", "prope.call_ledger.seams"})


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.prompt_readiness" if node.level else (node.module or "")
            imported.append((node.lineno, name))
    return imported


def _package_modules() -> list[Path]:
    modules = sorted(PACKAGE.rglob("*.py"))
    assert modules, f"no modules found under {PACKAGE}; the walk is looking in the wrong place"
    return modules


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_module_imports_a_prope_package_outside_the_allow_list(module: Path) -> None:
    offenders = [
        (line, name)
        for line, name in _imported_modules(module)
        if name.split(".")[0] == "prope"
        and not any(
            name == allowed or name.startswith(f"{allowed}.") for allowed in ALLOWED_PROPE_IMPORTS
        )
    ]
    assert offenders == [], f"{module.name}: {offenders}. {VIOLATION}"


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_module_names_a_forbidden_module_at_all(module: Path) -> None:
    """Names it, not merely imports it — a string is how the first one gets in.

    The allow-list above already refuses the import. This walks the raw source
    because `importlib.import_module("prope.release_control.commands")` is an
    import the AST walk above does not see, and *"we only need the status"* is
    exactly how the edge SR-1 forbids would arrive.
    """
    source = module.read_text(encoding="utf-8")
    named = [name for name in FORBIDDEN_MODULES if name in source]
    assert named == [], f"{module.name} names {named}. {VIOLATION}"


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_the_only_call_ledger_symbols_used_are_the_write_side(module: Path) -> None:
    """The direction, which the allow-list cannot express.

    `prope.call_ledger` is on the allow-list because the probe must pay for
    itself. What is forbidden is a READ — and a read is a different submodule of
    the same package, so only an enumeration catches it.
    """
    reached = {
        name
        for _, name in _imported_modules(module)
        if name.startswith("prope.call_ledger")
    }
    assert reached <= ALLOWED_CALL_LEDGER_MODULES, (
        f"{module.name} reaches {sorted(reached - ALLOWED_CALL_LEDGER_MODULES)}. call-ledger is a "
        "SINK (ADR-0018): this module hands over what a probe spent and never queries one back."
    )


def test_the_lock_and_this_file_agree_on_the_dependency_count() -> None:
    """A test naming five modules and a lock naming six would be silent drift.

    Read from the lock rather than restated here, so the two artifacts cannot
    disagree — the same rule `test_event_vocabulary_matches_the_locks` applies to
    the action vocabulary.
    """
    import yaml

    lock = PACKAGE.parents[2] / "docs" / "modules" / "prompt-readiness.lock.yml"
    spec = yaml.safe_load(lock.read_text(encoding="utf-8"))

    declared = set(spec["dependencies"])
    assert declared == {
        "prompt-registry",
        "evaluation",
        "provider-access",
        "access-control",
        "call-ledger",
    }, sorted(declared)

    forbidden = {entry["module"] for entry in spec["forbidden_dependencies"]}
    assert "release-control" in forbidden, (
        "SR-1's resolution — the lazy freeze — exists BECAUSE this edge is banned. "
        "A lock that stopped banning it would make the whole design arbitrary."
    )

"""`dependencies: [prompt-readiness, prompt-registry, evaluation, provider-access,
access-control, property-history]`, checked — and the two forbidden edges the
module's design turns on.

**call-ledger is forbidden in both directions, and the read side is the sharp
one.** ADR-0055's edge is prompt-registry → `prope.call_ledger.seams`, inbound and
per prompt, behind `prompt.read`. A direct edge from here would be the flat
cross-prompt reader ADR-0055 rejected by name — and worse, it would disclose the
existence of private prompts through a door nobody classified as a read (BR-01).
INT-043 extends the sanctioned path with a window instead of forking it, which is
why `summarise_prompt_calls` is imported from `prompt_registry.seams` and not from
the ledger that implements it.

**The write side is not reached either, and that took a change to get right.** The
gate spends the workspace's money, so somebody has to check the spend ceiling. The
first version checked it in `sweep.py`, which put a `call_ledger` import in this
package for the most defensible-sounding reason available. It now lives inside
`evaluation.gate`, beside the dispatches it guards — the same placement
`prompt_readiness.probe` uses, and for a better reason than tidiness: a ceiling
enforced by whichever caller remembered to ask has as many implementations as it
has callers.

**release-control is forbidden, which is why `accept` writes nothing.** A route
that recorded a disposition and created a revision would be this module reaching
into the approval chain; instead the route hands back a candidate body and the
person saves it themselves, through prompt-registry, under `revision.create`. The
non-negotiable is that no prompt reaches production without a recorded human
approval, and an accepted proposal is deliberately not one.

**provider-access is a declared dependency that must NOT be imported.** The lock
lists it because this module's work causes dispatches on the workspace's
credential and the cost is real. It is reached only through
`prompt_readiness.seams.run_probe` and `evaluation.seams.score_body_against_suite`,
both of which already carry the ceiling, the metering and the base-URL SSRF guard.
`tests/security/test_improvement_holds_no_outbound_capability.py` enforces the
absence; this file records why the lock and the import graph disagree on purpose.

**`prope.app_agent` is allowed and is not a seventh module.** It is the shared
runtime prompt-conversion, prompt-search and prompt-readiness already use — a
client, a circuit breaker and a DSPy runtime, not a bounded context.
"""

import ast
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_improvement"
LOCK = Path(__file__).resolve().parents[2] / "docs" / "modules" / "prompt-improvement.lock.yml"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        # The triage model's runtime. Shared infrastructure, not a bounded context.
        "prope.app_agent",
        "prope.db",
        # The management surface this module mounts on: A-045's error envelope and
        # its closed code vocabulary.
        "prope.dependencies",
        "prope.errors",
        "prope.evaluation",
        "prope.observability",
        # Shared parsers, not modules. `remedies` reads block structure and the
        # PLACEHOLDER regex from them ON PURPOSE (A-011, A-078): a second copy of
        # either would be a second definition of what a variable is, and SR-4's
        # round-trip would be asserting against the wrong one.
        "prope.canonical_prompt",
        "prope.prompt_composition",
        "prope.prompt_improvement",
        "prope.prompt_readiness",
        "prope.prompt_registry",
        "prope.property_history",
        "prope.session_auth",
    }
)

#: Named, not merely imported. A string is how the first one gets in —
#: `importlib.import_module("prope.call_ledger.reader")` is an import the AST walk
#: below does not see, and *"we only need the counts"* is exactly how the edge
#: ADR-0055 forbids would arrive.
FORBIDDEN_MODULES = (
    "prope.call_ledger",
    "prope.release_control",
    "prope.gateway",
    "prope.prompt_observation",
    "prope.chat_orchestrator",
    "prope.prompt_search",
    "prope.prompt_conversion",
)

VIOLATION = (
    "prompt-improvement declares six module dependencies. call-ledger is forbidden in BOTH "
    "directions — the read side because ADR-0055's one path out of the sink is per prompt "
    "through prompt-registry (INT-043 extends it with a window rather than forking it), the "
    "write side because the spend ceiling belongs inside the runner that spends. "
    "release-control is forbidden, which is why accepting a proposal writes no revision (SR-6). "
    "provider-access is a dependency and not an import: it is reached only through "
    "prompt-readiness's probe runner and evaluation's gate."
)


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.prompt_improvement" if node.level else (node.module or "")
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
    """Names it, not merely imports it. The allow-list above already refuses the import."""
    source = module.read_text(encoding="utf-8")
    named = [name for name in FORBIDDEN_MODULES if name in source]
    assert named == [], f"{module.name} names {named}. {VIOLATION}"


def test_the_windowed_metadata_read_goes_through_prompt_registry() -> None:
    """**The positive half of the call-ledger ban, which the absence cannot state.**

    A ban on importing the ledger is satisfied by a module that reads no traffic
    at all — and a module that read no traffic would have no detectors. So this
    asserts the seam that IS used: `summarise_prompt_calls`, imported from
    `prompt_registry.seams`, which is ADR-0055's sanctioned path with a window
    added to it.

    If somebody later moves that symbol back to a direct ledger import to *"cut
    out the middle module"*, the test above fails and this one explains what was
    lost: the permission check that happens in prompt-registry before the seam is
    reached, and the per-prompt shape that keeps a private prompt from being
    counted into somebody else's aggregate.
    """
    sweep = PACKAGE / "sweep.py"
    reached = {
        name for _, name in _imported_modules(sweep) if name.startswith("prope.prompt_registry")
    }

    assert "prope.prompt_registry.seams" in reached
    source = sweep.read_text(encoding="utf-8")
    assert "summarise_prompt_calls" in source


def test_the_lock_and_this_file_agree_on_the_dependency_list() -> None:
    """A test naming six modules and a lock naming seven would be silent drift.

    Read from the lock rather than restated here, so the two artefacts cannot
    disagree — the rule `test_event_vocabulary_matches_the_locks` applies to the
    action vocabulary, applied to the dependency list.
    """
    spec = yaml.safe_load(LOCK.read_text(encoding="utf-8"))

    assert set(spec["dependencies"]) == {
        "prompt-readiness",
        "prompt-registry",
        "evaluation",
        "provider-access",
        "access-control",
        "property-history",
    }, sorted(spec["dependencies"])

    forbidden = {entry["module"] for entry in spec["forbidden_dependencies"]}
    assert "call-ledger" in forbidden, (
        "INT-043 exists BECAUSE this edge is banned — it extends ADR-0055's per-prompt path with "
        "a window instead of opening a flat cross-prompt reader. A lock that stopped banning it "
        "would make the indirection arbitrary."
    )
    assert "release-control" in forbidden, (
        "SR-6 — accepting a proposal writes no revision — is a consequence of this ban. Without "
        "it, 'accept' becomes a button that ships a model-authored edit."
    )


def test_provider_access_is_declared_and_deliberately_unimported() -> None:
    """The one place the lock and the import graph disagree, asserted on purpose.

    A dependency that nothing imports usually means the lock is stale. Here it
    means the opposite: the module's work spends the workspace's provider credit,
    so the dependency is real and belongs in the lock — and the spending is done
    by two seams in other modules, so the import would be a third dispatch path
    without their ceiling, their metering or their SSRF guard.

    Asserting the absence here as well as in `tests/security` is deliberate. The
    security test says *this must not exist*; this one says *and it is missing on
    purpose, not by omission* — so nobody adds it to "fix" the lock.
    """
    spec = yaml.safe_load(LOCK.read_text(encoding="utf-8"))
    assert "provider-access" in spec["dependencies"]

    reached = {
        f"{module.name}:{line}"
        for module in _package_modules()
        for line, name in _imported_modules(module)
        if name.startswith("prope.provider_access")
    }
    assert reached == set(), (
        f"{sorted(reached)} — provider-access is reached through prompt-readiness's probe runner "
        "and evaluation's gate, both of which already meter and guard the dispatch."
    )


def test_the_module_reaches_property_history_only_to_append() -> None:
    """The sixth `writing_module`, and the narrowest possible edge to it.

    property-history is forbidden from depending on anything (its `target_id` and
    `actor_id` are values, not foreign keys), so the edge is one-way by
    construction. What this checks is the other end: this module writes and never
    reads. A read path into history would be this module deriving behaviour from
    the record it also writes, which is the shape that makes an audit log
    argue with itself.
    """
    reached = {
        name
        for module in _package_modules()
        for _, name in _imported_modules(module)
        if name.startswith("prope.property_history")
    }

    assert reached == {"prope.property_history.append", "prope.property_history.domain"}, sorted(
        reached
    )

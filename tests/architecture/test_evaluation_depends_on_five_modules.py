"""`dependencies: [prompt-registry, provider-access, call-ledger, access-control,
property-history]` as a checked property.

`docs/modules/evaluation.lock.yml` declares five module dependencies — four hard,
one soft — which is the most of any module in Prope, and names three forbidden
edges. Two of them are ordinary and one is a trap.

*gateway.* A-027 says the eval runner shares the *resolution and dispatch
semantics*, not the module. A batch path must never depend on the module carrying
the strictest latency budget in the system, and the shared thing —
`provider_access.dispatch` — is already imported directly.

*release-control.* This closes the cycle A-042 exists to break. Release-control
PULLS `get_review_summary()`; evaluation never pushes, never notifies, and never
learns whether its results were acted on.

*property-history — the trap.* That module appears in BOTH `dependencies`
(criticality: hard) and `forbidden_dependencies`, and the two say opposite things
unless the qualifier is read. What is forbidden is a **direct INSERT into
`history.history_event`**, not the edge and not INT-006. This module MUST call
`append()` and does so for four events; bypassing the writer would skip the
action registry, the per-action details allow-list (A-124) and the
`requires_reason` enforcement, and would produce an event nothing validated. The
lock says in as many words that an implementing agent reading
`forbidden_dependencies` literally would refuse to call `append()` at all, *"and
the failure would be a silent hole in the audit trail rather than a build
error"*. So this file asserts the distinction rather than the word: the writer is
imported, and `property_history.models` is not.

**`aio_pika` is forbidden and that is this module's one deviation made
checkable.** ADR-0049 declines the broker ADR-0028 bought — `eval_run.status` is
already a queue, and redelivery of an unacked message would re-dispatch every
paid case of a run nobody asked for. Evaluation is the first module to run in
`worker` without touching RabbitMQ, and an import here is how that would stop
being true.

**`prope.app_agent` and `prope.prompt_composition` are allowed and are not a
sixth and seventh module.** The first is the shared runtime — a client, a circuit
breaker and a DSPy runtime — that prompt-search, prompt-conversion,
prompt-improvement and prompt-readiness already reach on exactly these terms; the
second is a shared parser. Both entries are the ones
`test_prompt_readiness_depends_on_five_modules` and
`test_prompt_improvement_depends_on_six_modules` already carry, written here for
the same reason: a second copy of the PLACEHOLDER regex would be a second
definition of what a variable is, and it would eventually disagree with what
`render` substitutes.

FastAPI is permitted: this module mounts nine routes across eight paths.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "evaluation"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        # **A recorder, on `property_history`'s terms, and only through `seams`.**
        # `POST /runs` puts the dispatch on the activity timeline so a person can
        # see that a suite was started and by whom. That is an append this module
        # makes and never reads back — the timeline is served by agent-run's own
        # routes — which is the same relationship this list already grants
        # `prope.property_history`, and it is bounded the same way: the writer,
        # not the module. `AGENT_RUN_SURFACE` below is what keeps it there.
        #
        # This module reached `agent_run.repository` and `agent_run.domain`
        # directly until 2026-08-25 and this assertion was red for it. The edge
        # was always real; what it lacked was a door and a sentence.
        "prope.agent_run.seams",
        # The shared agent runtime — a client, a circuit breaker and a DSPy
        # runtime. Not a bounded context, and not a sixth module: prompt-search,
        # prompt-conversion, prompt-improvement and prompt-readiness already
        # reach it on the same terms. `generation.py` drafts assertions through
        # it and `dspy_program.py` compiles them.
        "prope.app_agent",
        "prope.call_ledger",
        "prope.db",
        "prope.dependencies",
        "prope.errors",
        "prope.evaluation",
        "prope.observability",
        # A shared parser, not a module — the same entry prompt-readiness and
        # prompt-improvement carry. `executor.py` renders a revision body with
        # the PLACEHOLDER regex the gateway substitutes against; a second copy
        # would be a second definition of what a variable is.
        "prope.prompt_composition",
        "prope.prompt_registry",
        "prope.property_history",
        "prope.provider_access",
        "prope.session_auth",
    }
)

FORBIDDEN_MODULES = (
    "prope.gateway",
    "prope.release_control",
)

VIOLATION = (
    "evaluation declares five module dependencies. The two forbidden edges run the other way or "
    "not at all: release-control PULLS get_review_summary() and is never called back (A-042, "
    "ADR-0005), and the gateway shares dispatch SEMANTICS rather than the module (A-027) — a "
    "batch path may not depend on the one carrying the strictest latency budget in the system."
)


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.evaluation" if node.level else (node.module or "")
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


def _all_imports() -> set[str]:
    return {name for module in _package_modules() for _, name in _imported_modules(module)}


AGENT_RUN_SURFACE = "prope.agent_run.seams"


def test_agent_run_is_reached_only_through_its_seam_module() -> None:
    """The timeline append, bounded to the three functions it was argued at.

    The allow-list above is a set of prefixes, so a later reader "tidying"
    `prope.agent_run.seams` to `prope.agent_run` would put `claim_runs` and
    `sync_claimed_run` in reach of a request handler — the executor's own lease
    machinery, which runs in `prope.worker` — and every other assertion in this
    file would still pass. This is the one that would not.
    """
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}
    reached = sorted(
        name
        for name in imported
        if name.split(".")[0] == "prope"
        and name.startswith("prope.agent_run")
        and name != AGENT_RUN_SURFACE
        and not name.startswith(f"{AGENT_RUN_SURFACE}.")
    )

    assert reached == [], (
        f"{reached} — evaluation records a run and never reads one back. "
        f"{AGENT_RUN_SURFACE} is the door; the worker's claim path is not behind it."
    )


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_module_imports_a_prope_package_outside_the_allow_list(module: Path) -> None:
    found = _forbidden_prope_imports(module)
    assert not found, f"{module.name}: {found} — {VIOLATION}"


def test_the_two_forbidden_modules_are_imported_at_no_depth() -> None:
    """Stated separately from the allow-list so the failure names the rule
    rather than only the missing entry."""
    reached = [
        name
        for name in _all_imports()
        for forbidden in FORBIDDEN_MODULES
        if name.startswith(forbidden)
    ]
    assert reached == [], f"{sorted(reached)} — {VIOLATION}"


def test_the_broker_client_is_imported_nowhere_in_this_module() -> None:
    """ADR-0049's deviation, as a property of the source rather than of a prose block.

    ``worker`` already consumes for call-ledger's drain and ``aio_pika`` is
    already a dependency of the project, so nothing but this assertion stops
    somebody reaching for the obvious option. The reason it is refused is
    specific rather than stylistic: an unacked message redelivered on a worker
    crash re-dispatches every case of a run, spending the workspace's own
    bring-your-own key on work nobody asked for — and AC-7 asserts *"no case is
    dispatched twice"*. Call-ledger's drain has the opposite shape and is
    idempotent on ``call_id``, which is why redelivery is a feature there and a
    bill here.
    """
    broker = [name for name in _all_imports() if name.split(".")[0] in {"aio_pika", "aiormq"}]

    assert broker == [], (
        f"{sorted(broker)}: evaluation declines the broker (ADR-0049). eval_run.status IS the "
        "queue, and a message beside it is a second queue that can disagree with it in both "
        "directions."
    )


def test_no_module_reaches_the_upstream_http_client() -> None:
    """A-043 and this module's ``external_services: []``.

    Every upstream call goes through provider-access, which holds the credential
    and never returns it (A-025). An ``httpx`` import here would be a second
    dispatch path with no admission gate, no SSRF guard and no failure
    classification — and A-095's error-versus-fail rule, which A-057 rests on,
    is provider-access's judgement rather than this module's to re-derive.
    """
    imported = _all_imports()

    assert not [
        name for name in imported if name.split(".")[0] in {"httpx", "openai", "requests"}
    ]


def test_history_is_written_through_the_validating_writer_and_never_by_table() -> None:
    """The `forbidden_dependencies` trap, asserted in both directions.

    The positive half matters as much as the negative one: a module that merely
    *lacks* an import of ``property_history.models`` is not yet a module that
    records its four events.
    """
    imported = _all_imports()

    assert "prope.property_history.append" in imported, (
        "evaluation MUST call append() — four events, in the same transaction as the state "
        "change they describe (ADR-0023). Its absence is a silent hole in the audit trail."
    )
    assert "prope.property_history.models" not in imported, (
        "a direct INSERT into history.history_event skips the action registry, the details "
        "allow-list (A-124) and requires_reason — an event nothing validated."
    )


def test_the_registry_is_reached_through_its_seams_and_not_its_internals() -> None:
    """INT-011 is a seam, and ``repository`` is somebody else's implementation.

    ``prompt_registry.seams`` is the module's declared public surface, and
    reaching past it — to ``repository``, ``commands`` or ``models`` — would let
    this module depend on a shape prompt-registry never promised. The one thing
    it needs beyond INT-011's registered three is ``get_prompt``, and that is a
    re-export **on the seam** rather than a reach around it, raised as OQ-145.
    """
    reached = sorted(
        name
        for name in _all_imports()
        if name.startswith("prope.prompt_registry.")
        and name not in {"prope.prompt_registry.seams", "prope.prompt_registry.domain"}
    )

    assert reached == [], f"evaluation reaches past prompt-registry's seam: {reached}"


def test_the_walk_found_modules_and_imports_to_inspect() -> None:
    modules = _package_modules()

    assert len(modules) >= 12, modules
    assert sum(len(_imported_modules(module)) for module in modules) >= 40


def test_the_walk_refuses_a_module_that_reaches_another_bounded_context(tmp_path: Path) -> None:
    """The guard is known to have teeth, proven on a file written here."""
    tempting = tmp_path / "tell_release_control_we_are_done.py"
    tempting.write_text(
        "from prope.release_control.seams import notify_review_ready\n"
        "from prope.db.session import workspace_transaction\n",
        encoding="utf-8",
    )

    assert _forbidden_prope_imports(tempting) == [(1, "prope.release_control.seams")]

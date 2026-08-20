"""Lane C. The measurement — and it is not an eval run.

**This is the file ADR-0067 is named for.** The card does not say *"this prompt
looks easy to inject"*; it says *"3 of 12 known injection cases were not
refused"*, because the twelve cases are ``builtin:chong-tiem-prompt@1`` — files
in the image, identical in every workspace, versioned with the product, scored by
the same deterministic assertions a hand-written suite uses. A test passes or it
fails, which dodges the entire question of whether an agent's opinion about a
prompt is trustworthy.

**It writes no ``evaluation.eval_run`` row, no ``dataset_attachment``, and no
cost delta** (SR-4). Reusing evaluation's runner is the cheap build and it breaks
that module's one non-negotiable in the place it is load-bearing: a probe's case
set is chosen by a declared profile and augmented by a drafter, a suite's is
chosen by a person, and *a model does not decide what a prompt is measured
against*. A probe measures readiness; a suite measures a release.

**The ceiling is checked once, before the first dispatch** (A-029), which is
where an eval run checks it and for the same reason: a refusal after the money is
spent is not a control. ``check_spend_ceiling`` fails OPEN by design (A-104) and
counts itself when it does; that trade is call-ledger's and this module inherits
it rather than second-guessing it.

**No fallback is requested or accepted** (A-164). A silent failover would measure
a model the released revision will not use, which is the one thing a probe must
not do. ``dispatch`` is called at ``priority=batch`` — a probe is nobody's
latency budget.

**An ``ERROR`` outcome is neither a refusal nor a leak.** A provider timeout is
not a guardrail win, and folding it into ``refused`` would report an outage as a
perfect score. That is why :class:`ProbeOutcome` has three members and the run
has three counters.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.call_ledger.domain import Outcome
from prope.call_ledger.seams import ProbeUsageRow, check_spend_ceiling, price_probe_usage
from prope.evaluation.assertions import CaseObservation, evaluate_all
from prope.evaluation.domain import CaseDraft, DatasetSpec
from prope.evaluation.executor import response_content
from prope.prompt_composition import compose
from prope.prompt_readiness import repository
from prope.prompt_readiness.catalogue import select_sets
from prope.prompt_readiness.domain import (
    MAX_EVIDENCE_CHARACTERS,
    ProbeOutcome,
    UsageProfile,
    redact_evidence,
)
from prope.prompt_readiness.observability import probe_cases_total, probe_runs_total
from prope.provider_access.seams import Priority, dispatch

log = structlog.get_logger(__name__)

__all__ = ["ProbeRefused", "ProbeTarget", "run_probe"]

#: One probe case gets this long. Generous, because `priority=batch` is not on
#: anybody's latency path, and bounded, because a run that never finishes leaves
#: a `running` row nothing will ever complete.
CASE_DEADLINE_MS = 60_000


class ProbeRefused(Exception):  # noqa: N818 - a refusal is not an error; see the docstring
    """The probe did not start. Carries the machine ``code`` the client renders.

    A refusal, not a failure: the workspace is over its ceiling, or the declared
    profile selects no set, or the revision has no binding to dispatch against.
    ADR-0053 means the client renders the ``code`` and not the message, so the
    code is the payload and the string is for the log line.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    """The candidate revision, as this lane needs it.

    Deliberately not ``RevisionRead``: that type carries the change summary, the
    author and the original body, none of which a dispatch loop has any use for,
    and a lane that accepted it would be a lane that could put them somewhere.
    """

    workspace_id: str
    prompt_id: str
    version_id: str
    body: str
    provider_config_id: str
    upstream_model: str
    parameters: dict[str, object]


async def run_probe(
    db: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    target: ProbeTarget,
    profile: UsageProfile,
    *,
    actor_id: str,
    now: datetime | None = None,
) -> str:
    """Dispatch the profile-selected sets against the revision. Returns the run id.

    Takes BOTH a session and a sessionmaker, and the asymmetry is call-ledger's
    rather than this module's: the ``readiness`` writes belong in the caller's
    transaction, and ``price_probe_usage`` must not — a seam that raised inside
    this transaction would take the ``probe_run`` row with it, and a probe whose
    spend was recorded but whose result was lost is the worst failure available.
    """
    started_at = now or datetime.now(UTC)

    specs = select_sets(profile)
    if not specs:
        # Not an error and not an empty run. A prompt declaring `internal` /
        # `none` has nothing here worth measuring, and writing a run that
        # dispatched nothing would put a meaningless zero on the card.
        probe_runs_total.labels(outcome="no_applicable_sets").inc()
        raise ProbeRefused("no_applicable_sets")

    decision = await check_spend_ceiling(sessionmaker, target.workspace_id, now=started_at)
    if not decision.allowed:
        probe_runs_total.labels(outcome="ceiling").inc()
        raise ProbeRefused("spend_ceiling_reached")

    run_id = f"prb_{ULID()}"
    await repository.create_probe_run(
        db,
        run_id=run_id,
        workspace_id=target.workspace_id,
        prompt_id=target.prompt_id,
        version_id=target.version_id,
        catalogue_ref=[spec.id for spec in specs],
        actor_id=actor_id,
        started_at=started_at,
    )

    counts = {outcome: 0 for outcome in ProbeOutcome}
    usage_rows: list[ProbeUsageRow] = []

    for spec in specs:
        for case in spec.cases:
            result, usage = await _run_case(sessionmaker, target, spec, case)
            counts[result.outcome] += 1
            probe_cases_total.labels(result=str(result.outcome)).inc()
            await repository.record_probe_case(db, run_id=run_id, result=result)
            if usage is not None:
                usage_rows.append(usage)

    # `partial` rather than `failed` while anything at all was measured: a run
    # where two dispatches timed out and ten did not still tells a reviewer
    # something, and calling it `failed` would throw that away.
    if counts[ProbeOutcome.ERROR] == 0:
        status = "completed"
    elif counts[ProbeOutcome.REFUSED] or counts[ProbeOutcome.LEAKED]:
        status = "partial"
    else:
        status = "failed"

    await repository.complete_probe_run(
        db,
        run_id=run_id,
        workspace_id=target.workspace_id,
        status=status,
        refused=counts[ProbeOutcome.REFUSED],
        leaked=counts[ProbeOutcome.LEAKED],
        errors=counts[ProbeOutcome.ERROR],
        completed_at=datetime.now(UTC),
    )
    probe_runs_total.labels(outcome=status).inc()

    # Outside the readiness writes and after them. See the docstring.
    await price_probe_usage(sessionmaker, usage_rows)

    log.info(
        "readiness.probe.completed",
        probe_run_id=run_id,
        status=status,
        cases=sum(counts.values()),
        leaked=counts[ProbeOutcome.LEAKED],
    )
    return run_id


@dataclass(frozen=True, slots=True)
class CaseResult:
    """One case's verdict, ready for ``readiness.probe_case_result``."""

    case_ref: str
    outcome: ProbeOutcome
    assertion_detail: str
    latency_ms: int | None
    call_id: str | None
    workspace_id: str


async def _run_case(
    sessionmaker: async_sessionmaker[AsyncSession],
    target: ProbeTarget,
    spec: DatasetSpec,
    case: CaseDraft,
) -> tuple[CaseResult, ProbeUsageRow | None]:
    """Dispatch one case and score it. Never raises.

    A case that cannot be composed, dispatched or scored becomes an ``ERROR``
    result and the run continues. The alternative — abandoning the run on the
    first provider hiccup — throws away every case that already succeeded, and
    those are the ones the reviewer is waiting for.
    """
    call_id = f"cal_{ULID()}"
    case_ref = f"{spec.id}#{case.name}"
    started = time.perf_counter()

    try:
        messages = compose(case.input_messages, target.body)
    except Exception as error:  # noqa: BLE001 - the case is scored, not the process
        return (
            _error(case_ref, target.workspace_id, call_id, type(error).__name__),
            None,
        )

    result = await dispatch(
        sessionmaker,
        workspace_id=target.workspace_id,
        provider_config_id=target.provider_config_id,
        upstream_model=target.upstream_model,
        parameters=target.parameters,
        messages=messages,
        deadline_ms=CASE_DEADLINE_MS,
        # A probe is nobody's latency budget, and it wants the truth about THIS
        # binding — so batch, and no fallback (A-164).
        priority=Priority.BATCH,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    if getattr(result, "error", None) is not None or not isinstance(
        getattr(result, "response", None), dict
    ):
        return (
            _error(case_ref, target.workspace_id, call_id, "dispatch_failed", latency_ms),
            None,
        )

    content = response_content(result.response)
    outcomes = evaluate_all(
        case.assertions, CaseObservation(content=content, latency_ms=latency_ms), spec.output_modality
    )
    # **A case fails only when the model actually COMPLIED.** The shipped sets
    # assert with a whole-output negative lookahead for exactly this reason (see
    # `common_datasets/00-README.md`): a refusal that QUOTES the injected
    # sentinel has other words around it and passes, because quoting is not
    # obeying and `forbidden_phrase` cannot tell the two apart.
    leaked = any(not outcome.passed for outcome in outcomes)

    detail = ""
    if leaked:
        # SR-7: redacted BEFORE storage, never at render. This string is derived
        # from provider output produced in response to a hostile input, which
        # makes it the one value in the module most worth distrusting.
        first = next(o for o in outcomes if not o.passed)
        detail = redact_evidence(f"{first.detail or ''} {(content or '')[:MAX_EVIDENCE_CHARACTERS]}")

    usage = result.usage
    return (
        CaseResult(
            case_ref=case_ref,
            outcome=ProbeOutcome.LEAKED if leaked else ProbeOutcome.REFUSED,
            assertion_detail=detail,
            latency_ms=latency_ms,
            call_id=call_id,
            workspace_id=target.workspace_id,
        ),
        ProbeUsageRow(
            call_id=call_id,
            workspace_id=target.workspace_id,
            prompt_id=target.prompt_id,
            version_id=target.version_id,
            provider_config_id=target.provider_config_id,
            upstream_model=target.upstream_model,
            # The LEDGER's outcome is about the CALL and not about the prompt: a
            # prompt that leaked still made a successful call, and recording it
            # as an error would make the spend look like a failure nobody should
            # have been billed for.
            outcome=Outcome.OK,
            created_at=datetime.now(UTC),
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        ),
    )


def _error(
    case_ref: str,
    workspace_id: str,
    call_id: str,
    reason: str,
    latency_ms: int | None = None,
) -> CaseResult:
    """An error result, with no ``call_id`` recorded against the ledger.

    ``call_id`` is kept on the readiness row so the two sides can be correlated
    if a record does turn up, and NO ``ProbeUsageRow`` is produced: a dispatch
    that failed before the provider answered spent nothing, and writing a
    zero-token record would put a call in the ledger that never happened.
    """
    return CaseResult(
        case_ref=case_ref,
        outcome=ProbeOutcome.ERROR,
        assertion_detail=redact_evidence(reason),
        latency_ms=latency_ms,
        call_id=call_id,
        workspace_id=workspace_id,
    )


def catalogue_refs(profile: UsageProfile) -> Sequence[str]:
    """Which set ids this profile would run. Used by the card to explain a probe offer."""
    return [spec.id for spec in select_sets(profile)]

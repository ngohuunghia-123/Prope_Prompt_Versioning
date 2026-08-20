"""The machine-side gate: score a CANDIDATE body against a suite, and record nothing.

**This lives in `evaluation` and not in `prompt-improvement`, and that placement
is the decision.** Compiling assertions, composing a case's messages and deciding
whether an output passed are this module's job; a second implementation next door
would be a second definition of *"passes the suite"*, and the one that drifted
would be the one nobody was reading. ADR-0068 §2 makes the gate load-bearing, so
it gets the real scorer rather than a lookalike.

**It writes no `eval_run` row, no `case_result` row and no attachment.** ADR-0067
§3's rule — *a probe is not an eval run* — applied to the same shape one step
later: this is not a run somebody asked for against a revision that exists, it is
arithmetic about a body that may never be saved. A row here would enter
release-control's cost delta and make a revision look more expensive because a
sweep ran overnight, and it would put a `version_id` on a run whose body is not
that version's.

**The candidate is never persisted anywhere.** :class:`CandidateRevision` carries
the four fields a dispatch needs and nothing else — no id, no status, no author —
so there is no shape here that could be mistaken for a revision or written as one.
prompt-improvement is forbidden from writing a revision at all (SR-6), and this
type is what makes that impossible rather than merely disallowed.

**The spend is the workspace's and lands as `source='probe'`.** It is a real
dispatch on the workspace's credential, and **the ceiling is checked HERE, before
the first case** — by the code that spends, never by the caller. `prompt_readiness.probe`
puts the check inside its runner for the same reason: a ceiling enforced by
whoever remembered to ask is a ceiling with as many implementations as callers,
and the one that forgot is the one that runs unattended overnight. It also keeps
prompt-improvement off `call_ledger` entirely, which its lock forbids by name.
That the gate spends at all is a stated cost of the design and the reason the
schedule that produces proposals is opt-in.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.call_ledger.domain import Outcome
from prope.call_ledger.seams import ProbeUsageRow, check_spend_ceiling, price_probe_usage
from prope.db.session import workspace_transaction
from prope.evaluation import repository
from prope.evaluation.domain import CaseOutcome
from prope.evaluation.executor import CALL_ID_PREFIX, CaseAttempt, _run_case
from prope.provider_access.domain import DispatchError, DispatchResult
from prope.provider_access.seams import dispatch

log = structlog.get_logger(__name__)

__all__ = [
    "CandidateRevision",
    "CaseVerdict",
    "GateResult",
    "SpendCeilingReached",
    "score_body_against_suite",
]


class SpendCeilingReached(Exception):  # noqa: N818 - a refusal, not a failure
    """The workspace is at its ceiling and the gate did not dispatch.

    Distinct from the ``None`` return, and the distinction is what a caller needs.
    ``None`` means *this candidate could not be gated* and the next one is worth
    trying; this means *stop spending for this workspace*, and a sweep that
    treated the two alike would run one ceiling check per remaining anomaly to
    learn the same thing each time.

    A refusal rather than an error: reaching a ceiling is the control working. It
    carries no figures, because the amount spent is not this caller's business.
    """

Dispatcher = Callable[..., Awaitable[DispatchResult | DispatchError]]

#: How many of a suite's cases run at once. Lower than a real run's, because the
#: gate runs unattended in `worker` beside every other workspace's gate and
#: nobody is waiting for it — spending the concurrency budget on latency here
#: buys nothing and competes with runs somebody IS waiting for.
GATE_CONCURRENCY = 2


@dataclass(frozen=True, slots=True)
class CandidateRevision:
    """A body to dispatch, shaped like the four fields a dispatch reads.

    Structurally compatible with :class:`prope.prompt_registry.domain.RevisionRead`
    where ``_run_case`` touches it, and deliberately nothing more. A type with an
    id and a status would be a revision-shaped object one refactor away from
    being saved as one.
    """

    body: str
    provider_config_id: str | None
    upstream_model: str | None
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CaseVerdict:
    """One case, both sides. The card renders these and not a verdict."""

    case_id: str
    name: str
    baseline: str | None
    candidate: str


@dataclass(frozen=True, slots=True)
class GateResult:
    """What the gate found, and whether the candidate may be shown to a person.

    ``regressed`` is the only field the queue consults, and it is computed the
    strict way on purpose: **a case that passed for the baseline and does not pass
    for the candidate is a regression, even if the candidate passes more cases
    overall.** A net-positive candidate that broke a case somebody wrote is
    exactly the 26/30 -> 9/30 shape — better on the dimensions measured in
    aggregate, worse on one that was.

    An ERROR on the candidate side counts as a regression too. *"The dispatch
    failed"* is not evidence the edit is safe, and treating an absence of a pass
    as a pass is how a gate stops being one.
    """

    suite_id: str
    suite_name: str
    case_count: int
    baseline_run_id: str | None
    baseline_pass: int
    candidate_pass: int
    candidate_error: int
    regressed: bool
    per_case: tuple[CaseVerdict, ...]

    def as_delta(self) -> dict[str, Any]:
        """The JSON the card renders and `improvement.proposal.gate_delta` stores."""
        return {
            "suite_id": self.suite_id,
            "suite_name": self.suite_name,
            "case_count": self.case_count,
            "baseline_run_id": self.baseline_run_id,
            "baseline_pass": self.baseline_pass,
            "candidate_pass": self.candidate_pass,
            "candidate_error": self.candidate_error,
            "cases": [
                {
                    "case_id": verdict.case_id,
                    "name": verdict.name,
                    "baseline": verdict.baseline,
                    "candidate": verdict.candidate,
                }
                for verdict in self.per_case
            ],
        }


def _usage_rows(
    attempts: Sequence[CaseAttempt],
    *,
    workspace_id: str,
    prompt_id: str,
    version_id: str,
    now: datetime,
) -> tuple[ProbeUsageRow, ...]:
    """The workspace's meter. ``ProbeUsageRow`` and never ``EvalUsageRow``.

    The type carries no ``run_id`` and cannot be given one, which is what keeps a
    gate run out of release-control's cost delta — the same property
    ``ck_call_record_probe_calls_name_no_run`` enforces at the other end.
    ``version_id`` is the RELEASED revision: the candidate has no id, and the
    spend is attributable to the revision whose degradation provoked it.
    """
    return tuple(
        ProbeUsageRow(
            call_id=f"{CALL_ID_PREFIX}{ULID()}",
            workspace_id=workspace_id,
            prompt_id=prompt_id,
            version_id=version_id,
            provider_config_id=attempt.provider_config_id,
            upstream_model=attempt.upstream_model,
            outcome=(
                Outcome.UPSTREAM_ERROR
                if attempt.outcome is CaseOutcome.ERROR
                else Outcome.OK
            ),
            created_at=now,
            input_tokens=attempt.input_tokens,
            output_tokens=attempt.output_tokens,
        )
        for attempt in attempts
        if attempt.dispatched
        and attempt.provider_config_id is not None
        and attempt.upstream_model is not None
    )


async def score_body_against_suite(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: str,
    prompt_id: str,
    version_id: str,
    suite_id: str,
    candidate: CandidateRevision,
    dispatcher: Dispatcher | None = None,
    now: datetime | None = None,
) -> GateResult | None:
    """Run one suite against ``candidate``. ``None`` when there is nothing to run.

    ``None`` — rather than an empty result — for a suite with no cases and for a
    candidate with no binding, because both mean *the gate did not happen* and a
    result object would let a caller read that as *the gate passed*. **SR-3 is the
    reason:** the whole control is that an ungated candidate never reaches a
    person, and the cheapest way to break it is a falsy result nobody checked.

    The baseline is the released revision's most recent COMPLETED run of the same
    suite. A prompt whose suite has never been run has no baseline, and then every
    case the candidate does not pass counts as a regression — the conservative
    direction, and the right one: with nothing to compare against, *"it passes 8
    of 10"* is not evidence that the two it fails were already failing.
    """
    at = now or datetime.now(UTC)
    # Resolved HERE and not in the signature's default. A default binds the
    # module global once, at import, so a caller that replaces `dispatch` —
    # every test of this gate does — would be replacing something this
    # function had already stopped reading. `prompt_readiness.probe` calls the
    # global directly for the same reason.
    send = dispatcher or dispatch

    if candidate.provider_config_id is None or candidate.upstream_model is None:
        return None

    # Before the suite is even loaded. A-104: `check_spend_ceiling` fails OPEN, so
    # this is a control against runaway spend and not a security boundary — but it
    # is the only thing standing between a nightly sweep and a provider bill, and
    # it belongs in front of the first read rather than in front of the first
    # dispatch, because loading a suite the gate will not run is wasted work too.
    decision = await check_spend_ceiling(sessionmaker, workspace_id, now=at)
    if not decision.allowed:
        log.info("evaluation.gate.skipped", workspace_id=workspace_id, reason="spend_ceiling")
        raise SpendCeilingReached()

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        suite = await repository.load_suite(db, suite_id)
        cases = await repository.list_cases(db, suite_id)
        baseline = await repository.latest_completed_run(db, version_id, suite_id)
        baseline_results = (
            await repository.list_case_results(db, baseline.id) if baseline else ()
        )

    if suite is None or not cases:
        return None

    modality = suite.output_modality
    gate = asyncio.Semaphore(GATE_CONCURRENCY)

    async def bounded(case: Any) -> CaseAttempt:
        async with gate:
            return await _run_case(
                sessionmaker,
                case,
                candidate,
                workspace_id=workspace_id,
                modality=modality,
                dispatcher=send,
            )

    started = time.perf_counter()
    attempts = await asyncio.gather(*(bounded(case) for case in cases))

    before: Mapping[str, str] = {
        result.case_id: str(result.outcome) for result in baseline_results
    }

    verdicts: list[CaseVerdict] = []
    regressed = False
    for case, attempt in zip(cases, attempts, strict=True):
        candidate_outcome = str(attempt.outcome)
        baseline_outcome = before.get(case.id)
        verdicts.append(
            CaseVerdict(
                case_id=case.id,
                name=case.name,
                baseline=baseline_outcome,
                candidate=candidate_outcome,
            )
        )
        # Strict. A case that passed and no longer does is a regression; so is a
        # case that errored on the candidate side, because a dispatch that failed
        # is not evidence the edit is safe. With no baseline, anything that is not
        # a pass counts — see the docstring.
        if attempt.outcome is not CaseOutcome.PASS and baseline_outcome in (
            None,
            str(CaseOutcome.PASS),
        ):
            regressed = True

    result = GateResult(
        suite_id=suite_id,
        suite_name=suite.name,
        case_count=len(cases),
        baseline_run_id=baseline.id if baseline else None,
        baseline_pass=sum(
            1 for outcome in before.values() if outcome == str(CaseOutcome.PASS)
        ),
        candidate_pass=sum(
            1 for attempt in attempts if attempt.outcome is CaseOutcome.PASS
        ),
        candidate_error=sum(
            1 for attempt in attempts if attempt.outcome is CaseOutcome.ERROR
        ),
        regressed=regressed,
        per_case=tuple(verdicts),
    )

    # Outside the read transaction and after the scoring, for `price_probe_usage`'s
    # stated reason (D-19): a seam that raised inside the caller's transaction
    # would take the result with it, and a gate whose spend was recorded and whose
    # verdict was lost is the worst of the available failures.
    await price_probe_usage(
        sessionmaker,
        _usage_rows(
            attempts,
            workspace_id=workspace_id,
            prompt_id=prompt_id,
            version_id=version_id,
            now=at,
        ),
    )

    # Counts and ids only. No case name, no output, no body — A-046's rule, and
    # the reason `test_no_content_reaches_a_log_line_by_construction.py` can walk
    # this file.
    log.info(
        "evaluation.gate.scored",
        suite_id=suite_id,
        cases=len(cases),
        duration_seconds=round(time.perf_counter() - started, 3),
    )
    return result

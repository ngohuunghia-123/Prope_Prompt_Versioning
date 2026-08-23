"""The daily pass. One workspace at a time, under its own policy, writing nothing when nothing is wrong.

**ADR-0051's shape rule, and its reason.** Workspaces are enumerated through
``access.list_workspaces()`` — one of the four sanctioned ``SECURITY DEFINER``
functions, and no fifth is added — and every data read happens inside
``workspace_transaction``, under the deny-by-default policy. The alternative, one
query across every tenant, does not merely leak: under ADR-0045 it returns **zero
rows**, and a sweep built on it would run cleanly, find nothing, and look healthy.
That is the failure this shape exists to make impossible, which is why
``prompts_scanned_total`` is a metric — a pass that scanned nothing and a pass
that found nothing produce the same empty inbox and different numbers there.

**Zero anomalies writes nothing and says nothing.** An empty inbox is the SUCCESS
condition — A-162's inversion, reused from ADR-0064. A module that always found
something would be a module whose findings mean nothing.

**The first sweep on a workspace emits ONE summary row and no findings.** Two
hundred items on the first screen anybody sees is deck 6 slide 64 arriving fully
formed, and an inbox nobody can face is an inbox nobody opens again.
``improvement.sweep.is_first_sweep`` makes that a property of the data rather than
of a code path somebody can regress, and revision 0033 withholds DELETE on that
table so a retention job can never make a dormant workspace look new.

**The sweep proposes and never performs.** It opens findings, and where an anomaly
makes an edit family reachable AND the prompt has a suite AND the candidate clears
that suite without regression, it opens ONE proposal. It never writes a revision,
never submits, never approves and never releases (SR-6), and the rate cap that
stops it flooding a queue is a database index rather than a check in this file.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.db.session import workspace_transaction
from prope.evaluation.seams import (
    CandidateRevision,
    SpendCeilingReached,
    score_body_against_suite,
    suites_for_prompt,
)
from prope.prompt_improvement import repository
from prope.prompt_improvement.detectors import (
    profile_drift,
    released_but_unused,
    run_ledger_detectors,
)
from prope.prompt_improvement.domain import (
    PROPOSAL_TTL,
    WINDOW,
    Anomaly,
    ProposalStatus,
    RemedyKind,
    WindowPair,
)
from prope.prompt_improvement.observability import (
    findings_total,
    gate_rejected_total,
    prompts_scanned_total,
    proposals_total,
    sweep_duration_seconds,
)
from prope.prompt_improvement.remedies import RemedyRefused
from prope.prompt_improvement.remedies import apply as apply_remedy
from prope.prompt_improvement.triage import Triaged, triage_anomalies
from prope.prompt_registry.domain import PromptRow
from prope.prompt_registry.seams import (
    get_revision,
    list_released_prompts,
    summarise_prompt_calls,
)
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft

log = structlog.get_logger(__name__)

__all__ = ["JOB_NAME", "sweep_all_workspaces", "sweep_workspace"]

#: The supervisor's task name, and the ``job`` field on a ``supervisor.job_crashed``
#: line. A closed set fixed in source, which is what makes it safe as a log field
#: under A-046.
JOB_NAME = "improvement_sweep"

#: The four axes, by the name they carry on both `prompt_property` and `revision`.
#: Written out rather than derived from the profile type, because this comparison
#: is between two dicts of STRINGS read from two tables — introducing the enum
#: here would mean a value the enum has not learned yet compares unequal to
#: itself and raises a drift finding on a deploy.
PROFILE_AXES = ("audience", "untrusted_input", "acts", "sensitivity")


def _profile(source: Any) -> dict[str, str]:
    return {axis: getattr(source, axis, "undeclared") for axis in PROFILE_AXES}


async def sweep_all_workspaces(
    sessionmaker: async_sessionmaker[AsyncSession], *, now: datetime | None = None
) -> None:
    """One pass over every workspace. Called on a timer from ``worker``.

    A workspace whose pass raises does not stop the others. The sweep is a
    best-effort daily measurement, and one workspace with a broken provider
    configuration must not mean nobody else's traffic is looked at — the failure
    is logged with the workspace id, which is a log FIELD rather than a metric
    label for ADR-0030's reason.
    """
    at = now or datetime.now(UTC)

    for workspace_id in await list_workspace_ids(sessionmaker):
        try:
            await sweep_workspace(sessionmaker, workspace_id, now=at)
        except Exception:
            log.exception("improvement.sweep.failed", workspace_id=workspace_id)


async def sweep_workspace(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    *,
    now: datetime | None = None,
) -> None:
    """One workspace's pass, end to end.

    Three transactions rather than one, and the split is deliberate. The first
    expires proposals and appends their history events; the second reads and
    detects; the third writes findings and proposals. A single long transaction
    would hold row locks on ``improvement.finding`` across every gate dispatch in
    the workspace — minutes of provider latency — and an inbox read would block
    behind a sweep nobody is waiting for.
    """
    at = now or datetime.now(UTC)
    started = time.perf_counter()
    window_start = at - WINDOW
    prior_start = window_start - WINDOW

    await _expire_proposals(sessionmaker, workspace_id, at)

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        first_sweep = not await repository.has_ever_swept(db, workspace_id=workspace_id)
        prompts = await list_released_prompts(db, workspace_id)

        detected: list[tuple[PromptRow, tuple[Anomaly, ...], Any]] = []
        for prompt in prompts:
            anomalies, revision = await _detect(
                db,
                prompt,
                window_start=window_start,
                prior_start=prior_start,
                window_end=at,
                now=at,
            )
            prompts_scanned_total.inc()
            if anomalies:
                detected.append((prompt, anomalies, revision))

    findings_opened = 0
    if not first_sweep:
        for prompt, anomalies, revision in detected:
            findings_opened += await _record(
                sessionmaker, workspace_id, prompt, anomalies, revision, at
            )
    else:
        # The first pass measures and reports a total. The findings are NOT
        # written, so tomorrow's pass opens them one recurrence at a time against
        # a person who has already been told the shape of the backlog.
        log.info(
            "improvement.sweep.first_pass",
            workspace_id=workspace_id,
            prompts=len(prompts),
            degraded=len(detected),
        )

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await repository.record_sweep(
            db,
            workspace_id=workspace_id,
            window_start=window_start,
            window_end=at,
            prompts_scanned=len(prompts),
            findings_opened=findings_opened,
            is_first_sweep=first_sweep,
            now=at,
        )

    sweep_duration_seconds.observe(time.perf_counter() - started)


async def _detect(
    db: AsyncSession,
    prompt: PromptRow,
    *,
    window_start: datetime,
    prior_start: datetime,
    window_end: datetime,
    now: datetime,
) -> tuple[tuple[Anomaly, ...], Any]:
    """Every detector for one prompt. Reads metadata and a revision, never a body's traffic."""
    current = await summarise_prompt_calls(
        db, prompt.id, window_start=window_start, window_end=window_end
    )
    prior = await summarise_prompt_calls(
        db, prompt.id, window_start=prior_start, window_end=window_start
    )
    windows = WindowPair(current=current, prior=prior)

    anomalies = list(run_ledger_detectors(windows))

    unused = released_but_unused(windows, released_at=prompt.released_at, now=now)
    if unused is not None:
        anomalies.append(unused)

    revision = (
        await get_revision(db, prompt.released_version_id)
        if prompt.released_version_id
        else None
    )
    if revision is not None:
        drift = profile_drift(_profile(prompt), _profile(revision))
        if drift is not None:
            anomalies.append(drift)

    return tuple(anomalies), revision


async def _record(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    prompt: PromptRow,
    anomalies: Sequence[Anomaly],
    revision: Any,
    now: datetime,
) -> int:
    """Triage, open findings, and try for at most one proposal. Returns findings opened."""
    triaged = await triage_anomalies(
        anomalies,
        prompt_title=prompt.title,
        prompt_body=revision.body if revision is not None else "",
    )

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        opened: list[tuple[Triaged, str]] = []
        for entry in triaged:
            finding_id, occurrences = await repository.open_or_bump_finding(
                db,
                workspace_id=workspace_id,
                prompt_id=prompt.id,
                anomaly=entry.anomaly,
                evidence_line=entry.evidence,
                now=now,
            )
            if occurrences == 1:
                findings_total.labels(
                    detector_id=str(entry.anomaly.detector_id),
                    severity=str(entry.anomaly.severity),
                ).inc()
            opened.append((entry, finding_id))

        await repository.resolve_absent_findings(
            db,
            workspace_id=workspace_id,
            prompt_id=prompt.id,
            still_firing=[entry.anomaly.detector_id for entry in triaged],
        )

    await _propose(sessionmaker, workspace_id, prompt, revision, opened, now)
    return sum(1 for _entry, _id in opened)


async def _propose(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    prompt: PromptRow,
    revision: Any,
    opened: Sequence[tuple[Triaged, str]],
    now: datetime,
) -> None:
    """At most one proposal, for the highest-ranked anomaly that can carry one.

    **The order of the checks is the design.** Suite existence is tested before a
    candidate is built, and the candidate is built and validated before the gate
    spends anything — so a prompt with no suite costs nothing, and a transform
    that would not round-trip costs nothing either. The expensive step is last on
    purpose.
    """
    if revision is None:
        return

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        suites = [suite for suite in await suites_for_prompt(db, prompt.id) if suite.case_count]

    for entry, finding_id in opened:
        kind = entry.anomaly.remedy_kind

        if kind is not RemedyKind.EDIT or entry.family is None:
            continue

        # **SR-3, absolute.** No suite means the edit branch is unreachable for
        # every family and every anomaly, and the remedy degrades to proposing
        # the cases that would make a future edit gateable at all.
        if not suites:
            await _open(
                sessionmaker,
                workspace_id,
                prompt,
                finding_id,
                RemedyKind.CASE,
                None,
                None,
                None,
                None,
                now,
            )
            return

        try:
            candidate_body = apply_remedy(revision.body, entry.family)
        except RemedyRefused as refused:
            log.info(
                "improvement.remedy.refused",
                remedy_family=str(entry.family),
                code=refused.code,
            )
            continue

        # The ceiling lives inside the gate, with the code that spends — this
        # module holds no `call_ledger` edge at all, in either direction, which
        # its lock forbids by name. A refusal stops the prompt rather than moving
        # to the next anomaly: the workspace is out of money, and asking again
        # per anomaly would learn the same thing several times.
        try:
            result = await score_body_against_suite(
                sessionmaker,
                workspace_id=workspace_id,
                prompt_id=prompt.id,
                version_id=revision.version_id,
                suite_id=suites[0].id,
                candidate=CandidateRevision(
                    body=candidate_body,
                    provider_config_id=revision.provider_config_id,
                    upstream_model=revision.upstream_model,
                    parameters=revision.parameters,
                ),
                now=now,
            )
        except SpendCeilingReached:
            log.info("improvement.gate.skipped", workspace_id=workspace_id, reason="ceiling")
            return

        # `None` is *the gate did not happen*, and it is treated as a rejection.
        # A falsy result read as a pass is the cheapest available way to break the
        # one control this module exists around.
        if result is None or result.regressed:
            gate_rejected_total.labels(remedy_family=str(entry.family)).inc()
            log.info(
                "improvement.gate.rejected",
                remedy_family=str(entry.family),
                ran=result is not None,
            )
            continue

        await _open(
            sessionmaker,
            workspace_id,
            prompt,
            finding_id,
            RemedyKind.EDIT,
            entry.family,
            candidate_body,
            result.baseline_run_id,
            result.as_delta(),
            now,
        )
        return


async def _open(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    prompt: PromptRow,
    finding_id: str,
    kind: RemedyKind,
    family: Any,
    candidate_body: str | None,
    gate_run_id: str | None,
    gate_delta: dict[str, Any] | None,
    now: datetime,
) -> None:
    """One proposal, or nothing if the prompt's single open slot is taken (SR-2)."""
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        proposal_id = await repository.open_proposal(
            db,
            workspace_id=workspace_id,
            prompt_id=prompt.id,
            finding_id=finding_id,
            remedy_kind=kind,
            remedy_family=family,
            candidate_body=candidate_body,
            gate_run_id=gate_run_id,
            gate_delta=gate_delta,
            expires_at=now + PROPOSAL_TTL,
            now=now,
        )

    proposals_total.labels(
        remedy_family=str(family) if family else str(kind),
        disposition="opened" if proposal_id else "rate_capped",
    ).inc()


async def _expire_proposals(
    sessionmaker: async_sessionmaker[AsyncSession], workspace_id: str, now: datetime
) -> None:
    """Close what nobody decided, and record each one in the trail.

    **The finding stays open** (OQ-158). A finding is a fact and a proposal is an
    offer: if the fact is still true, this same pass bumps its occurrence count a
    moment later and the rate-cap slot the expiry just freed admits a fresh offer.

    ``actor_type='system'`` with a NULL ``actor_id`` — the only event in this
    module's vocabulary with no human actor. Nobody decided, and inventing a
    service account to attribute it to would be a lie with a name.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        expired = await repository.close_expired_proposals(
            db, workspace_id=workspace_id, now=now
        )
        for row in expired:
            await append(
                db,
                HistoryEventDraft(
                    workspace_id=workspace_id,
                    actor_type=ActorType.SYSTEM,
                    action="improvement_proposal_expired",
                    target_type="property",
                    target_id=row["prompt_id"],
                    scope_prompt_id=row["prompt_id"],
                    occurred_at=now,
                    details={
                        "proposal_id": row["id"],
                        "remedy_family": row["remedy_family"] or "",
                    },
                ),
            )
            proposals_total.labels(
                remedy_family=row["remedy_family"] or "note",
                disposition=str(ProposalStatus.EXPIRED),
            ).inc()

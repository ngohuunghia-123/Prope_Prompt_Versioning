"""The scheduled re-probe: run the shipped guardrail sets against what is LIVE.

**This is the evidence source the detectors cannot be.** Deck 6 slide 25's drift
is a guardrail that became bypassable because the provider changed the model
underneath it, and it has **no error attached to it** — the calls succeed, the
latency is normal, the cost is normal, and every ledger detector in this module
reads healthy. The only way to notice is to ask the question again.

**It costs the workspace money, so it is opt-in and it is not on by default.**
``improvement.schedule.enabled`` is FALSE until somebody sets it on a screen that
shows the estimated weekly cost first (A-166), the route declares
``spend_ceiling.manage`` because enabling a recurring charge is a spending
decision before it is an authoring one, and ``check_spend_ceiling`` runs before
the first dispatch of every run.

**The probe runner is `prompt-readiness`'s and is reused verbatim.** A second
dispatch loop here would be a second definition of *"refused 11 of 12"* and the
one that drifted would be the one nobody was reading — which would also make the
comparison this job exists for meaningless, because the two sides would be
measuring different things.

**The comparison is against the PREVIOUS completed run of the same version**, read
before this one starts. Both must have completed: a provider outage is not a
guardrail regression, and reporting one as the other sends somebody to fix the
wrong thing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.db.session import workspace_transaction
from prope.prompt_improvement import repository
from prope.prompt_improvement.detectors import probe_leak_appeared
from prope.prompt_improvement.domain import DEFAULT_CADENCE_DAYS
from prope.prompt_improvement.observability import findings_total
from prope.prompt_readiness.domain import UsageProfile
from prope.prompt_readiness.seams import (
    ProbeRefused,
    ProbeTarget,
    latest_probe_run,
    run_probe,
)
from prope.prompt_registry.domain import PromptRow
from prope.prompt_registry.seams import get_revision, list_released_prompts

log = structlog.get_logger(__name__)

__all__ = ["JOB_NAME", "PROBE_ACTOR", "run_scheduled_probes", "selects"]

JOB_NAME = "improvement_reprobe"

#: The ``actor_id`` stamped on a scheduled ``readiness.probe_run``. A literal
#: rather than a seeded ``access.user`` row, and the distinction matters: a user
#: row could be granted permissions, tombstoned, or mistaken for a person in an
#: audit. This is a value in a column that is documented as a value (ADR-0054),
#: and it reads as what it is — *nobody pressed a button; a schedule did*.
PROBE_ACTOR = "system:improvement_schedule"


def selects(schedule: dict[str, Any], prompt: PromptRow) -> bool:
    """Does this workspace's schedule cover this prompt?

    Empty ``namespaces`` and empty ``prompt_ids`` with ``enabled`` true means
    EVERY released prompt. That is a deliberate choice a person makes on a screen
    showing the estimated weekly cost, not an accident of two empty arrays — and
    it is written here as one branch so it cannot become an accident later.
    """
    if not schedule.get("enabled"):
        return False
    namespaces = tuple(schedule.get("namespaces") or ())
    prompt_ids = tuple(schedule.get("prompt_ids") or ())
    if not namespaces and not prompt_ids:
        return True
    return prompt.id in prompt_ids or prompt.namespace in namespaces


def _due(schedule: dict[str, Any], now: datetime) -> bool:
    last_run = schedule.get("last_run_at")
    if last_run is None:
        return True
    cadence = int(schedule.get("cadence_days") or DEFAULT_CADENCE_DAYS)
    return now - last_run >= timedelta(days=cadence)


async def run_scheduled_probes(
    sessionmaker: async_sessionmaker[AsyncSession], *, now: datetime | None = None
) -> None:
    """One pass over every workspace that opted in and is due.

    A workspace whose pass raises does not stop the others, for
    ``sweep_all_workspaces``'s reason. ADR-0051's enumerate-then-read shape again:
    an unscoped query under ADR-0045 would return zero rows and this job would
    look like it was working.
    """
    at = now or datetime.now(UTC)

    for workspace_id in await list_workspace_ids(sessionmaker):
        try:
            await reprobe_workspace(sessionmaker, workspace_id, now=at)
        except Exception:
            log.exception("improvement.reprobe.failed", workspace_id=workspace_id)


async def reprobe_workspace(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    *,
    now: datetime | None = None,
) -> None:
    at = now or datetime.now(UTC)

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        schedule = await repository.read_schedule(db, workspace_id=workspace_id)

    if schedule is None or not _due(schedule, at):
        return

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        prompts = [
            prompt
            for prompt in await list_released_prompts(db, workspace_id)
            if selects(schedule, prompt)
        ]

    for prompt in prompts:
        await _reprobe(sessionmaker, workspace_id, prompt, at)

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await repository.mark_schedule_run(db, workspace_id=workspace_id, now=at)


async def _reprobe(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    prompt: PromptRow,
    now: datetime,
) -> None:
    """One prompt: read the prior run, probe, compare, open a finding if it leaked."""
    version_id = prompt.released_version_id
    if version_id is None:
        return

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        prior = await latest_probe_run(db, workspace_id=workspace_id, version_id=version_id)
        revision = await get_revision(db, version_id)

    if revision is None or not revision.provider_config_id or not revision.upstream_model:
        return

    # The RELEASED revision's stamped profile, not the property's current one.
    # The probe measures what is serving, so it selects its sets from what was
    # approved — and the disagreement between the two is `profile_drift`'s
    # finding, raised by the sweep, not silently resolved here in favour of one.
    profile = UsageProfile.from_row(revision)

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        try:
            await run_probe(
                db,
                sessionmaker,
                ProbeTarget(
                    workspace_id=workspace_id,
                    prompt_id=prompt.id,
                    version_id=version_id,
                    body=revision.body,
                    provider_config_id=revision.provider_config_id,
                    upstream_model=revision.upstream_model,
                    parameters=revision.parameters,
                ),
                profile,
                actor_id=PROBE_ACTOR,
                now=now,
            )
        except ProbeRefused as refused:
            # Over the ceiling, or the profile selects no set. Neither is an
            # error and neither is a finding — a prompt declaring `internal` /
            # `none` has nothing here worth measuring, and saying so as an
            # anomaly would be the module inventing work.
            log.info(
                "improvement.reprobe.refused", workspace_id=workspace_id, code=refused.code
            )
            return

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        current = await latest_probe_run(db, workspace_id=workspace_id, version_id=version_id)

    if current is None or prior is None:
        # The first scheduled probe of a revision establishes the baseline and
        # reports nothing. There is no *"it used to refuse this"* yet, and
        # opening a finding on the first measurement would report the guardrail's
        # existing state as a regression.
        return
    if current["status"] != "completed" or prior["status"] != "completed":
        return

    cases = current["refused_count"] + current["leaked_count"] + current["error_count"]
    anomaly = probe_leak_appeared(
        current_leaked=current["leaked_count"],
        prior_leaked=prior["leaked_count"],
        cases=cases,
    )
    if anomaly is None:
        return

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        _finding_id, occurrences = await repository.open_or_bump_finding(
            db,
            workspace_id=workspace_id,
            prompt_id=prompt.id,
            anomaly=anomaly,
            evidence_line=None,
            now=now,
        )

    if occurrences == 1:
        findings_total.labels(
            detector_id=str(anomaly.detector_id), severity=str(anomaly.severity)
        ).inc()

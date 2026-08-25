"""Every statement this module issues. Text SQL with bound parameters, never f-strings.

``tests/architecture/test_no_sql_interpolation.py`` walks ``src/prope/`` with
``ast`` and refuses an interpolated string reaching ``text()``. That gate covers
this file from the day it lands, which is the point of the rule being written
that way rather than per module.

**Every statement filters by ``workspace_id`` even though RLS already does.** The
policy is the guarantee and the predicate is the belt: ADR-0045 makes a missing
filter return zero rows rather than somebody else's, so the redundancy costs an
index lookup and buys a query that is still correct when read on its own.

**The freeze is an ``ON CONFLICT DO NOTHING`` followed by a read** (SR-1). Two
card reads of a just-submitted revision race by construction — the write is
triggered by a read, so any two readers can arrive together — and the arbiter is
``uq_readiness_report_version``, not an application-level "does it exist yet"
check, which is the race rather than the fix.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.prompt_readiness.domain import CATALOGUE_VERSION, Finding, RuleId, UsageProfile

if TYPE_CHECKING:  # pragma: no cover - a type-only edge, not an import edge
    from prope.prompt_readiness.probe import CaseResult

__all__ = [
    "coverage_for_prompt",
    "complete_probe_run",
    "create_probe_run",
    "dismissals_for_prompt",
    "freeze_report",
    "latest_probe_run",
    "read_cached_lane_b",
    "read_frozen_report",
    "record_dismissal",
    "record_probe_case",
    "remove_dismissal",
    "write_cached_lane_b",
]


DISMISSALS_FOR_PROMPT = text("""
    SELECT rule_id, reason, actor_id, created_at
      FROM readiness.dismissal
     WHERE workspace_id = :workspace_id
       AND prompt_id = :prompt_id
""")

RECORD_DISMISSAL = text("""
    INSERT INTO readiness.dismissal
        (workspace_id, prompt_id, rule_id, reason, actor_id, created_at)
    VALUES
        (:workspace_id, :prompt_id, :rule_id, :reason, :actor_id, :created_at)
    ON CONFLICT (workspace_id, prompt_id, rule_id) DO NOTHING
""")

REMOVE_DISMISSAL = text("""
    DELETE FROM readiness.dismissal
     WHERE workspace_id = :workspace_id
       AND prompt_id = :prompt_id
       AND rule_id = :rule_id
""")

READ_FROZEN_REPORT = text("""
    SELECT id, profile_snapshot, rendered_findings, catalogue_version, created_at
      FROM readiness.report
     WHERE workspace_id = :workspace_id
       AND version_id = :version_id
""")

#: **The card's count without the card.** ``rendered_findings`` is the frozen
#: evidence a reviewer reads; a caller that only needs to know *how many* has no
#: business pulling the JSONB across to measure it, and one that pulled it would
#: hold every finding's text in a module that has no surface to show them on.
#:
#: Keyed on ``version_id`` like :data:`READ_FROZEN_REPORT` and not additionally on
#: ``prompt_id``: a version belongs to exactly one prompt, so the second
#: predicate would be a redundancy that reads like a safeguard.
COUNT_FROZEN_FINDINGS = text("""
    SELECT jsonb_array_length(rendered_findings)::integer
      FROM readiness.report
     WHERE workspace_id = :workspace_id
       AND version_id = :version_id
""")

#: ``DO NOTHING`` and then a re-read, never ``RETURNING`` alone. A conflicting
#: insert returns no row, and a caller that treated that as failure would 500 on
#: the second of two simultaneous card reads — which is the ordinary case, not
#: the edge one.
FREEZE_REPORT = text("""
    INSERT INTO readiness.report
        (id, workspace_id, prompt_id, version_id, profile_snapshot,
         rendered_findings, catalogue_version, created_at)
    VALUES
        (:id, :workspace_id, :prompt_id, :version_id, CAST(:profile_snapshot AS jsonb),
         CAST(:rendered_findings AS jsonb), :catalogue_version, :created_at)
    ON CONFLICT (workspace_id, version_id) DO NOTHING
""")

CREATE_PROBE_RUN = text("""
    INSERT INTO readiness.probe_run
        (id, workspace_id, prompt_id, version_id, catalogue_ref, status,
         refused_count, leaked_count, error_count, actor_id, started_at)
    VALUES
        (:id, :workspace_id, :prompt_id, :version_id, :catalogue_ref, 'running',
         0, 0, 0, :actor_id, :started_at)
""")

COMPLETE_PROBE_RUN = text("""
    UPDATE readiness.probe_run
       SET status = :status,
           refused_count = :refused,
           leaked_count = :leaked,
           error_count = :errors,
           completed_at = :completed_at
     WHERE workspace_id = :workspace_id
       AND id = :id
""")

RECORD_PROBE_CASE = text("""
    INSERT INTO readiness.probe_case_result
        (id, workspace_id, probe_run_id, case_ref, outcome,
         assertion_detail, latency_ms, call_id, created_at)
    VALUES
        (:id, :workspace_id, :probe_run_id, :case_ref, :outcome,
         :assertion_detail, :latency_ms, :call_id, :created_at)
""")

#: Newest completed run for this revision. `completed_at DESC NULLS LAST` so a
#: run still in flight never shadows the finished one a reviewer is reading.
LATEST_PROBE_RUN = text("""
    SELECT id, catalogue_ref, status, refused_count, leaked_count,
           error_count, started_at, completed_at
      FROM readiness.probe_run
     WHERE workspace_id = :workspace_id
       AND version_id = :version_id
     ORDER BY completed_at DESC NULLS LAST, started_at DESC
     LIMIT 1
""")

READ_LANE_B_CACHE = text("""
    SELECT findings, model
      FROM readiness.lane_b_cache
     WHERE workspace_id = :workspace_id
       AND fingerprint = :fingerprint
""")

WRITE_LANE_B_CACHE = text("""
    INSERT INTO readiness.lane_b_cache
        (workspace_id, fingerprint, findings, model, created_at)
    VALUES
        (:workspace_id, :fingerprint, CAST(:findings AS jsonb), :model, :created_at)
    ON CONFLICT (workspace_id, fingerprint) DO NOTHING
""")

#: Evaluation's numbers. ``DISTINCT ON (name) ... ORDER BY name, suite_version
#: DESC`` is `evaluation.repository.LIST_CURRENT_SUITES`'s own shape, copied
#: rather than imported: a suite is versioned and only the newest of each name is
#: current, and counting every version would tell an author they have nine suites
#: when they have one they have edited eight times.
#:
#: Read across the schema boundary by a **query and not a join** — no readiness
#: table appears here, so this is a read of another module's rows under its own
#: tenant policy rather than a relationship between two schemas.
COVERAGE_FOR_PROMPT = text("""
    WITH current_suite AS (
        SELECT DISTINCT ON (name) id, case_count
          FROM evaluation.eval_suite
         WHERE workspace_id = :workspace_id
           AND prompt_id = :prompt_id
         ORDER BY name, suite_version DESC
    )
    SELECT count(*)                         AS suite_count,
           coalesce(sum(case_count), 0)     AS case_count
      FROM current_suite
""")


async def dismissals_for_prompt(
    db: AsyncSession, *, workspace_id: str, prompt_id: str
) -> dict[str, Mapping[str, Any]]:
    """Dismissed rules for this prompt, keyed by ``rule_id``.

    Per prompt and NOT per revision, which is the whole point (D-04): a dismissal
    that expired on every save would be a nag with extra steps. A rule the
    catalogue no longer contains is dropped here rather than rendered — SR-9's
    unknown-code rule, applied to stored data as well as to generated data.
    """
    rows = (
        await db.execute(DISMISSALS_FOR_PROMPT, {"workspace_id": workspace_id, "prompt_id": prompt_id})
    ).mappings()
    known = {str(rule) for rule in RuleId}
    return {row["rule_id"]: dict(row) for row in rows if row["rule_id"] in known}


async def record_dismissal(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_id: str,
    rule_id: RuleId,
    reason: str,
    actor_id: str,
    now: datetime | None = None,
) -> None:
    await db.execute(
        RECORD_DISMISSAL,
        {
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "rule_id": str(rule_id),
            "reason": reason,
            "actor_id": actor_id,
            "created_at": now or datetime.now(UTC),
        },
    )


async def remove_dismissal(
    db: AsyncSession, *, workspace_id: str, prompt_id: str, rule_id: RuleId
) -> None:
    """Un-dismiss. The reason ``dismissal`` holds a DELETE grant and ``report`` does not."""
    await db.execute(
        REMOVE_DISMISSAL,
        {"workspace_id": workspace_id, "prompt_id": prompt_id, "rule_id": str(rule_id)},
    )


async def read_frozen_report(
    db: AsyncSession, *, workspace_id: str, version_id: str
) -> Mapping[str, Any] | None:
    row = (
        await db.execute(READ_FROZEN_REPORT, {"workspace_id": workspace_id, "version_id": version_id})
    ).mappings().first()
    return dict(row) if row else None


async def count_frozen_findings(
    db: AsyncSession, *, workspace_id: str, version_id: str
) -> int | None:
    """How many findings the frozen report carries, or ``None`` if there is none.

    **``None`` and ``0`` are different answers and both are ordinary.** No report
    means nobody has opened the card for this revision yet; a report with zero
    findings means somebody did and it was clean. A caller that coalesced them
    would render "no attention needed" for a revision nothing has looked at.
    """
    return (
        await db.execute(
            COUNT_FROZEN_FINDINGS, {"workspace_id": workspace_id, "version_id": version_id}
        )
    ).scalar_one_or_none()


async def freeze_report(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_id: str,
    version_id: str,
    profile: UsageProfile,
    findings: Sequence[Finding],
    now: datetime | None = None,
) -> Mapping[str, Any]:
    """Write the reviewer's copy once, then return whichever copy won. SR-1.

    Returns the stored row rather than what was passed in, and that is the whole
    contract: the loser of a race must see the winner's bytes, or two reviewers
    reading the same revision would be looking at two different cards while both
    believing the card is frozen.
    """
    await db.execute(
        FREEZE_REPORT,
        {
            "id": f"rdr_{ULID()}",
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "version_id": version_id,
            "profile_snapshot": json.dumps(profile.as_dict()),
            "rendered_findings": json.dumps([finding.as_dict() for finding in findings]),
            "catalogue_version": CATALOGUE_VERSION,
            "created_at": now or datetime.now(UTC),
        },
    )
    stored = await read_frozen_report(db, workspace_id=workspace_id, version_id=version_id)
    if stored is None:  # pragma: no cover - the insert either landed or conflicted
        raise RuntimeError(
            f"readiness report for {version_id} is neither inserted nor present; the unique "
            "constraint is the only thing that can refuse the insert and it implies a row"
        )
    return stored


async def create_probe_run(
    db: AsyncSession,
    *,
    run_id: str,
    workspace_id: str,
    prompt_id: str,
    version_id: str,
    catalogue_ref: Sequence[str],
    actor_id: str,
    started_at: datetime,
) -> None:
    await db.execute(
        CREATE_PROBE_RUN,
        {
            "id": run_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "version_id": version_id,
            "catalogue_ref": list(catalogue_ref),
            "actor_id": actor_id,
            "started_at": started_at,
        },
    )


async def record_probe_case(db: AsyncSession, *, run_id: str, result: "CaseResult") -> None:
    await db.execute(
        RECORD_PROBE_CASE,
        {
            "id": f"prc_{ULID()}",
            "workspace_id": result.workspace_id,
            "probe_run_id": run_id,
            "case_ref": result.case_ref,
            "outcome": str(result.outcome),
            "assertion_detail": result.assertion_detail,
            "latency_ms": result.latency_ms,
            "call_id": result.call_id,
            "created_at": datetime.now(UTC),
        },
    )


async def complete_probe_run(
    db: AsyncSession,
    *,
    run_id: str,
    workspace_id: str,
    status: str,
    refused: int,
    leaked: int,
    errors: int,
    completed_at: datetime,
) -> None:
    await db.execute(
        COMPLETE_PROBE_RUN,
        {
            "id": run_id,
            "workspace_id": workspace_id,
            "status": status,
            "refused": refused,
            "leaked": leaked,
            "errors": errors,
            "completed_at": completed_at,
        },
    )


async def latest_probe_run(
    db: AsyncSession, *, workspace_id: str, version_id: str
) -> Mapping[str, Any] | None:
    row = (
        await db.execute(LATEST_PROBE_RUN, {"workspace_id": workspace_id, "version_id": version_id})
    ).mappings().first()
    return dict(row) if row else None


async def read_cached_lane_b(
    db: AsyncSession, *, workspace_id: str, fingerprint: str
) -> Sequence[Mapping[str, Any]] | None:
    row = (
        await db.execute(READ_LANE_B_CACHE, {"workspace_id": workspace_id, "fingerprint": fingerprint})
    ).mappings().first()
    return list(row["findings"]) if row else None


async def write_cached_lane_b(
    db: AsyncSession,
    *,
    workspace_id: str,
    fingerprint: str,
    findings: Sequence[Mapping[str, Any]],
    model: str,
) -> None:
    await db.execute(
        WRITE_LANE_B_CACHE,
        {
            "workspace_id": workspace_id,
            "fingerprint": fingerprint,
            "findings": json.dumps(list(findings)),
            "model": model,
            "created_at": datetime.now(UTC),
        },
    )


async def coverage_for_prompt(
    db: AsyncSession, *, workspace_id: str, prompt_id: str
) -> tuple[int, int]:
    """``(suite_count, case_count)`` for Lane A's coverage rule."""
    row = (
        await db.execute(COVERAGE_FOR_PROMPT, {"workspace_id": workspace_id, "prompt_id": prompt_id})
    ).mappings().first()
    if row is None:
        return (0, 0)
    return (int(row["suite_count"] or 0), int(row["case_count"] or 0))

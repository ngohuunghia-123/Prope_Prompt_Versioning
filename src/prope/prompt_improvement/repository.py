"""Every statement this module issues. Text SQL with bound parameters, never f-strings.

``tests/architecture/test_no_sql_interpolation.py`` walks ``src/prope/`` with
``ast`` and refuses an interpolated string reaching ``text()``. That gate covers
this file from the day it lands, which is the point of the rule being written
that way rather than per module.

**Every statement filters by ``workspace_id`` even though RLS already does.** The
policy is the guarantee and the predicate is the belt: ADR-0045 makes a missing
filter return zero rows rather than somebody else's, so the redundancy costs an
index lookup and buys a query that is still correct when read on its own.

**Two writes lean on a partial unique index rather than on a read-then-write**,
and both are controls rather than optimisations. :func:`open_or_bump_finding` is
an ``ON CONFLICT DO UPDATE`` against
``uq_improvement_finding_one_open_per_detector``, so a recurrence bumps a count
under concurrency instead of racing two sweeps into two rows.
:func:`open_proposal` is an ``ON CONFLICT DO NOTHING`` against
``uq_improvement_proposal_one_open_per_prompt`` — SR-2's rate cap — and it
returns ``None`` when the slot is taken, because *a second proposal waits* is an
ordinary outcome and not an error.

**The inbox is TWO statements and never a join onto ``registry``.** The obvious
single query would join ``registry.prompt_property`` for the reader's own
``owner_id`` / ``access_level`` clauses — and that is the cross-schema read
ADR-0055 refuses and this module's lock forbids by name. So
:func:`prompts_with_open_findings` answers *which prompts have something to say*,
the route authorises each one through the seam it is allowed to use, and
:func:`list_inbox` reads back only the ids that survived. A prompt the reader
cannot see contributes NOTHING — not a redacted row, not a count, not a total
that differs (A-116, SR-7) — because it never reaches the second statement.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.prompt_improvement.domain import (
    Anomaly,
    DetectorId,
    ProposalStatus,
    RemedyFamily,
    RemedyKind,
)

__all__ = [
    "close_expired_proposals",
    "decide_proposal",
    "dismiss_finding",
    "findings_for_prompt",
    "has_ever_swept",
    "list_inbox",
    "mark_schedule_run",
    "open_or_bump_finding",
    "open_proposal",
    "prompts_with_open_findings",
    "read_finding",
    "read_proposal",
    "read_schedule",
    "record_sweep",
    "resolve_absent_findings",
    "upsert_schedule",
]

#: ``ON CONFLICT`` against the partial unique index, so two sweeps racing produce
#: one row and a bumped count. ``severity`` and ``params`` are refreshed because
#: the newest arithmetic is the arithmetic worth rendering; ``evidence_line`` is
#: refreshed only when the caller has one, so a sweep whose triage model was down
#: does not blank a sentence an earlier sweep already wrote.
OPEN_OR_BUMP_FINDING = text("""
    INSERT INTO improvement.finding
        (id, workspace_id, prompt_id, detector_id, severity, params, evidence_line,
         first_seen, last_seen, occurrence_count, status, created_at)
    VALUES
        (:id, :workspace_id, :prompt_id, :detector_id, :severity, CAST(:params AS jsonb),
         :evidence_line, :seen_at, :seen_at, 1, 'open', :seen_at)
    ON CONFLICT (workspace_id, prompt_id, detector_id) WHERE status = 'open'
    DO UPDATE SET
        last_seen        = EXCLUDED.last_seen,
        occurrence_count = improvement.finding.occurrence_count + 1,
        severity         = EXCLUDED.severity,
        params           = EXCLUDED.params,
        evidence_line    = COALESCE(EXCLUDED.evidence_line, improvement.finding.evidence_line)
    RETURNING id, occurrence_count
""")

#: The signal went away. Written by the SWEEP and never by a person, which is what
#: keeps the dismissal rate per detector honest — a finding that fixed itself must
#: not read as one somebody rejected, because those two numbers argue for opposite
#: things (retire the detector / leave it alone).
RESOLVE_ABSENT_FINDINGS = text("""
    UPDATE improvement.finding
       SET status = 'resolved'
     WHERE workspace_id = :workspace_id
       AND prompt_id = :prompt_id
       AND status = 'open'
       AND NOT (detector_id = ANY(:still_firing))
""")

READ_FINDING = text("""
    SELECT id, workspace_id, prompt_id, detector_id, severity, params, evidence_line,
           first_seen, last_seen, occurrence_count, status,
           dismissed_reason, dismissed_by, dismissed_at
      FROM improvement.finding
     WHERE workspace_id = :workspace_id
       AND id = :finding_id
""")

DISMISS_FINDING = text("""
    UPDATE improvement.finding
       SET status = 'dismissed',
           dismissed_reason = :reason,
           dismissed_by = :actor_id,
           dismissed_at = :now
     WHERE workspace_id = :workspace_id
       AND id = :finding_id
       AND status = 'open'
    RETURNING id, prompt_id, detector_id
""")

#: SR-2. ``DO NOTHING`` and a ``RETURNING`` that comes back empty when the slot is
#: taken — the rate cap answering, in the database, without the application ever
#: asking whether it may.
OPEN_PROPOSAL = text("""
    INSERT INTO improvement.proposal
        (id, workspace_id, prompt_id, finding_id, remedy_kind, remedy_family,
         candidate_body, gate_run_id, gate_delta, status, expires_at, created_at)
    VALUES
        (:id, :workspace_id, :prompt_id, :finding_id, :remedy_kind, :remedy_family,
         :candidate_body, :gate_run_id, CAST(:gate_delta AS jsonb), 'open',
         :expires_at, :created_at)
    ON CONFLICT (workspace_id, prompt_id) WHERE status = 'open'
    DO NOTHING
    RETURNING id
""")

READ_PROPOSAL = text("""
    SELECT id, workspace_id, prompt_id, finding_id, remedy_kind, remedy_family,
           candidate_body, gate_run_id, gate_delta, status, decided_by, decided_at,
           expires_at, created_at
      FROM improvement.proposal
     WHERE workspace_id = :workspace_id
       AND id = :proposal_id
""")

DECIDE_PROPOSAL = text("""
    UPDATE improvement.proposal
       SET status = :status,
           decided_by = :actor_id,
           decided_at = :now
     WHERE workspace_id = :workspace_id
       AND id = :proposal_id
       AND status = 'open'
    RETURNING id, prompt_id, finding_id, remedy_family, candidate_body
""")

#: Expiry closes the PROPOSAL and leaves the finding open (OQ-158). ``decided_by``
#: stays NULL — ``ck_improvement_proposal_a_decision_has_an_actor`` exempts
#: ``expired`` for exactly this reason: nobody decided, and inventing a service
#: account to attribute it to would be a lie with a name.
CLOSE_EXPIRED_PROPOSALS = text("""
    UPDATE improvement.proposal
       SET status = 'expired'
     WHERE workspace_id = :workspace_id
       AND status = 'open'
       AND expires_at <= :now
    RETURNING id, remedy_family, prompt_id, finding_id
""")

#: Step one of the inbox: which prompts have an open finding at all. Ids only —
#: no detector, no evidence, no count — so the list the route authorises against
#: discloses nothing beyond *this prompt has something*, and the route drops the
#: ones the reader may not see before any of that is read.
PROMPTS_WITH_OPEN_FINDINGS = text("""
    SELECT DISTINCT prompt_id
      FROM improvement.finding
     WHERE workspace_id = :workspace_id
       AND status = 'open'
     LIMIT :limit
""")

#: Step two: the findings for the ids that survived authorisation.
#:
#: **No join onto ``registry``**, which is the point. The reader's visibility is
#: decided by ``may()`` against a prompt row the route loaded through
#: prompt-registry's seam — ADR-0020's rule that a permission decision takes the
#: subject's attributes from the caller — and re-deciding it here with a SQL
#: predicate over another module's table would be a second answer that can
#: disagree with the first.
LIST_INBOX = text("""
    SELECT f.id, f.prompt_id, f.detector_id, f.severity, f.params, f.evidence_line,
           f.first_seen, f.last_seen, f.occurrence_count, f.status,
           p.id AS proposal_id, p.remedy_kind, p.remedy_family, p.gate_delta, p.expires_at
      FROM improvement.finding f
      LEFT JOIN improvement.proposal p
             ON p.workspace_id = f.workspace_id
            AND p.finding_id = f.id
            AND p.status = 'open'
     WHERE f.workspace_id = :workspace_id
       AND f.status = 'open'
       AND f.prompt_id = ANY(:prompt_ids)
     ORDER BY f.last_seen DESC, f.id DESC
     LIMIT :limit
""")

FINDINGS_FOR_PROMPT = text("""
    SELECT f.id, f.prompt_id, f.detector_id, f.severity, f.params, f.evidence_line,
           f.first_seen, f.last_seen, f.occurrence_count, f.status,
           p.id AS proposal_id, p.remedy_kind, p.remedy_family, p.gate_delta, p.expires_at
      FROM improvement.finding f
      LEFT JOIN improvement.proposal p
             ON p.workspace_id = f.workspace_id
            AND p.finding_id = f.id
            AND p.status = 'open'
     WHERE f.workspace_id = :workspace_id
       AND f.prompt_id = :prompt_id
     ORDER BY f.status, f.last_seen DESC
     LIMIT :limit
""")

RECORD_SWEEP = text("""
    INSERT INTO improvement.sweep
        (id, workspace_id, window_start, window_end, prompts_scanned, findings_opened,
         is_first_sweep, completed_at)
    VALUES
        (:id, :workspace_id, :window_start, :window_end, :prompts_scanned,
         :findings_opened, :is_first_sweep, :completed_at)
""")

#: ``EXISTS`` rather than ``count(*)``, because the question is whether this
#: workspace has EVER been swept and a count would read every row to answer it.
HAS_EVER_SWEPT = text("""
    SELECT EXISTS (
        SELECT 1 FROM improvement.sweep WHERE workspace_id = :workspace_id
    )
""")

READ_SCHEDULE = text("""
    SELECT workspace_id, enabled, cadence_days, namespaces, prompt_ids,
           last_run_at, updated_by, updated_at
      FROM improvement.schedule
     WHERE workspace_id = :workspace_id
""")

UPSERT_SCHEDULE = text("""
    INSERT INTO improvement.schedule
        (workspace_id, enabled, cadence_days, namespaces, prompt_ids, updated_by, updated_at)
    VALUES
        (:workspace_id, :enabled, :cadence_days, :namespaces, :prompt_ids, :actor_id, :now)
    ON CONFLICT (workspace_id) DO UPDATE SET
        enabled      = EXCLUDED.enabled,
        cadence_days = EXCLUDED.cadence_days,
        namespaces   = EXCLUDED.namespaces,
        prompt_ids   = EXCLUDED.prompt_ids,
        updated_by   = EXCLUDED.updated_by,
        updated_at   = EXCLUDED.updated_at
    RETURNING workspace_id, enabled, cadence_days, namespaces, prompt_ids,
              last_run_at, updated_by, updated_at
""")

MARK_SCHEDULE_RUN = text("""
    UPDATE improvement.schedule
       SET last_run_at = :now
     WHERE workspace_id = :workspace_id
""")


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


async def open_or_bump_finding(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_id: str,
    anomaly: Anomaly,
    evidence_line: str | None,
    now: datetime | None = None,
) -> tuple[str, int]:
    """``(finding_id, occurrence_count)``. One row per open (prompt, detector).

    A recurrence is a BUMP and not a second row, so an inbox says *"this has
    happened 14 times"* rather than showing fourteen items — the same alert-fatigue
    prescription deck 6 slide 64 makes about pages, applied to the data model
    instead of to a render.
    """
    seen_at = _now(now)
    row = (
        await db.execute(
            OPEN_OR_BUMP_FINDING,
            {
                "id": f"fnd_{ULID()}",
                "workspace_id": workspace_id,
                "prompt_id": prompt_id,
                "detector_id": str(anomaly.detector_id),
                "severity": str(anomaly.severity),
                "params": json.dumps(anomaly.params, default=str),
                "evidence_line": evidence_line,
                "seen_at": seen_at,
            },
        )
    ).mappings().one()
    return row["id"], row["occurrence_count"]


async def resolve_absent_findings(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_id: str,
    still_firing: Sequence[DetectorId],
) -> None:
    """Close open findings whose detector did not fire this pass."""
    await db.execute(
        RESOLVE_ABSENT_FINDINGS,
        {
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "still_firing": [str(detector) for detector in still_firing],
        },
    )


async def read_finding(
    db: AsyncSession, *, workspace_id: str, finding_id: str
) -> Mapping[str, Any] | None:
    """One finding by id, with no visibility decision taken.

    The route loads this to learn which PROMPT the finding is about, then
    authorises against that prompt through the registry seam — ADR-0020's order.
    A finding id that belongs to another workspace returns ``None`` because the
    tenant policy answers zero rows, which is the not-found this module's refusal
    shape wants anyway.
    """
    row = (
        await db.execute(READ_FINDING, {"workspace_id": workspace_id, "finding_id": finding_id})
    ).mappings().first()
    return dict(row) if row else None


async def dismiss_finding(
    db: AsyncSession,
    *,
    workspace_id: str,
    finding_id: str,
    reason: str,
    actor_id: str,
    now: datetime | None = None,
) -> Mapping[str, Any] | None:
    row = (
        await db.execute(
            DISMISS_FINDING,
            {
                "workspace_id": workspace_id,
                "finding_id": finding_id,
                "reason": reason,
                "actor_id": actor_id,
                "now": _now(now),
            },
        )
    ).mappings().first()
    return dict(row) if row else None


async def open_proposal(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_id: str,
    finding_id: str,
    remedy_kind: RemedyKind,
    remedy_family: RemedyFamily | None,
    candidate_body: str | None,
    gate_run_id: str | None,
    gate_delta: Mapping[str, Any] | None,
    expires_at: datetime,
    now: datetime | None = None,
) -> str | None:
    """The proposal id, or ``None`` when the prompt's one open slot is taken.

    ``None`` is an ordinary outcome and not an error: SR-2 says *a second waits*,
    and the caller counts it rather than raising. The slot frees when the open
    proposal is accepted, dismissed or expires.
    """
    row = (
        await db.execute(
            OPEN_PROPOSAL,
            {
                "id": f"prp_{ULID()}",
                "workspace_id": workspace_id,
                "prompt_id": prompt_id,
                "finding_id": finding_id,
                "remedy_kind": str(remedy_kind),
                "remedy_family": str(remedy_family) if remedy_family else None,
                "candidate_body": candidate_body,
                "gate_run_id": gate_run_id,
                "gate_delta": json.dumps(gate_delta, default=str) if gate_delta else None,
                "expires_at": expires_at,
                "created_at": _now(now),
            },
        )
    ).mappings().first()
    return row["id"] if row else None


async def read_proposal(
    db: AsyncSession, *, workspace_id: str, proposal_id: str
) -> Mapping[str, Any] | None:
    row = (
        await db.execute(
            READ_PROPOSAL, {"workspace_id": workspace_id, "proposal_id": proposal_id}
        )
    ).mappings().first()
    return dict(row) if row else None


async def decide_proposal(
    db: AsyncSession,
    *,
    workspace_id: str,
    proposal_id: str,
    status: ProposalStatus,
    actor_id: str,
    now: datetime | None = None,
) -> Mapping[str, Any] | None:
    """Accept or dismiss. Returns ``None`` if it was already decided.

    **The accept path writes NO revision** (SR-6). This marks the disposition and
    hands back ``candidate_body``; the write is prompt-registry's
    ``create_revision`` on a separate, explicit request under ``revision.create``.
    """
    row = (
        await db.execute(
            DECIDE_PROPOSAL,
            {
                "workspace_id": workspace_id,
                "proposal_id": proposal_id,
                "status": str(status),
                "actor_id": actor_id,
                "now": _now(now),
            },
        )
    ).mappings().first()
    return dict(row) if row else None


async def close_expired_proposals(
    db: AsyncSession, *, workspace_id: str, now: datetime | None = None
) -> tuple[Mapping[str, Any], ...]:
    rows = (
        await db.execute(
            CLOSE_EXPIRED_PROPOSALS, {"workspace_id": workspace_id, "now": _now(now)}
        )
    ).mappings().all()
    return tuple(dict(row) for row in rows)


async def prompts_with_open_findings(
    db: AsyncSession, *, workspace_id: str, limit: int = 200
) -> tuple[str, ...]:
    """Prompt ids with at least one open finding. The route authorises each.

    Bounded, because the authorisation loop after it is one prompt read per id and
    an unbounded list would make an inbox read scale with a workspace's worst
    week. A workspace with more than ``limit`` degraded prompts has a bigger
    problem than pagination.
    """
    rows = (
        await db.execute(
            PROMPTS_WITH_OPEN_FINDINGS, {"workspace_id": workspace_id, "limit": limit}
        )
    ).scalars().all()
    return tuple(rows)


async def list_inbox(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_ids: Sequence[str],
    limit: int = 50,
) -> tuple[Mapping[str, Any], ...]:
    """Open findings for prompts the reader has already been allowed to see.

    An empty ``prompt_ids`` returns an empty tuple without a round trip that could
    have been observed as slower than one with results — the timing half of
    A-116's byte-identical property, which costs one branch here.
    """
    if not prompt_ids:
        return ()
    rows = (
        await db.execute(
            LIST_INBOX,
            {
                "workspace_id": workspace_id,
                "prompt_ids": list(prompt_ids),
                "limit": limit,
            },
        )
    ).mappings().all()
    return tuple(dict(row) for row in rows)


async def findings_for_prompt(
    db: AsyncSession, *, workspace_id: str, prompt_id: str, limit: int = 50
) -> tuple[Mapping[str, Any], ...]:
    """The per-prompt tab. **No visibility filter here, and that is correct.**

    The route has already authorised ``prompt.read`` against the prompt row it
    loaded (ADR-0020), and re-deciding the same question with a different
    mechanism is how two answers start disagreeing. The inbox filters because it
    reads across prompts; this one reads inside a decision already taken.
    """
    rows = (
        await db.execute(
            FINDINGS_FOR_PROMPT,
            {"workspace_id": workspace_id, "prompt_id": prompt_id, "limit": limit},
        )
    ).mappings().all()
    return tuple(dict(row) for row in rows)


async def has_ever_swept(db: AsyncSession, *, workspace_id: str) -> bool:
    return bool(await db.scalar(HAS_EVER_SWEPT, {"workspace_id": workspace_id}))


async def record_sweep(
    db: AsyncSession,
    *,
    workspace_id: str,
    window_start: datetime,
    window_end: datetime,
    prompts_scanned: int,
    findings_opened: int,
    is_first_sweep: bool,
    now: datetime | None = None,
) -> str:
    """The pass's own record. Written at COMPLETION, never at start.

    An interrupted pass therefore leaves no row and the next one re-reads the same
    window — which is safe because findings dedupe on ``(prompt, detector)``, so a
    re-read bumps a count rather than duplicating. A row written at start would
    make a crashed pass indistinguishable from a completed empty one, and the
    second is this module's success condition.
    """
    sweep_id = f"swp_{ULID()}"
    await db.execute(
        RECORD_SWEEP,
        {
            "id": sweep_id,
            "workspace_id": workspace_id,
            "window_start": window_start,
            "window_end": window_end,
            "prompts_scanned": prompts_scanned,
            "findings_opened": findings_opened,
            "is_first_sweep": is_first_sweep,
            "completed_at": _now(now),
        },
    )
    return sweep_id


async def read_schedule(
    db: AsyncSession, *, workspace_id: str
) -> Mapping[str, Any] | None:
    row = (
        await db.execute(READ_SCHEDULE, {"workspace_id": workspace_id})
    ).mappings().first()
    return dict(row) if row else None


async def upsert_schedule(
    db: AsyncSession,
    *,
    workspace_id: str,
    enabled: bool,
    cadence_days: int,
    namespaces: Sequence[str],
    prompt_ids: Sequence[str],
    actor_id: str,
    now: datetime | None = None,
) -> Mapping[str, Any]:
    row = (
        await db.execute(
            UPSERT_SCHEDULE,
            {
                "workspace_id": workspace_id,
                "enabled": enabled,
                "cadence_days": cadence_days,
                "namespaces": list(namespaces),
                "prompt_ids": list(prompt_ids),
                "actor_id": actor_id,
                "now": _now(now),
            },
        )
    ).mappings().one()
    return dict(row)


async def mark_schedule_run(
    db: AsyncSession, *, workspace_id: str, now: datetime | None = None
) -> None:
    await db.execute(MARK_SCHEDULE_RUN, {"workspace_id": workspace_id, "now": _now(now)})

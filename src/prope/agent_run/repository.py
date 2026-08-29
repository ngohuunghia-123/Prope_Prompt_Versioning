from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.agent_run.domain import PLAN_CATALOGUE, PlanBasis, RunKind, RunStatus
from prope.evaluation.seams import run_progress

INSERT_RUN = text("""
    INSERT INTO agent.run
        (id, workspace_id, requested_by, kind, plan_basis, status, prompt_id,
         version_id, source_refs, result_actions, idempotency_key, created_at, updated_at)
    VALUES
        (:id, :workspace_id, :requested_by, :kind, :plan_basis, 'queued', :prompt_id,
         :version_id, CAST(:source_refs AS jsonb), CAST(:result_actions AS jsonb),
         :idempotency_key, :now, :now)
    ON CONFLICT (workspace_id, idempotency_key) DO NOTHING
    RETURNING id
""")
READ_BY_KEY = text("""
    SELECT id FROM agent.run
    WHERE workspace_id = :workspace_id AND idempotency_key = :idempotency_key
""")
INSERT_NODE = text("""
    INSERT INTO agent.node
        (run_id, workspace_id, id, sequence, capability, kind, status,
         idempotency_key, evidence_refs)
    VALUES
        (:run_id, :workspace_id, :id, :sequence, :capability, :kind, 'pending',
         :idempotency_key, '[]'::jsonb)
""")
INSERT_EDGE = text("""
    INSERT INTO agent.edge (run_id, workspace_id, source_node_id, target_node_id)
    VALUES (:run_id, :workspace_id, :source, :target)
""")
READ_RUN = text("""
    SELECT id, kind, plan_basis, status, prompt_id, version_id, source_refs,
           result_actions, progress_current, progress_total, progress_unit,
           acknowledged_at, created_at, updated_at, started_at, finished_at
    FROM agent.run
    WHERE workspace_id = :workspace_id AND requested_by = :requested_by AND id = :run_id
""")
LIST_RUNS = text("""
    SELECT id, kind, plan_basis, status, prompt_id, version_id, source_refs,
           result_actions, progress_current, progress_total, progress_unit,
           acknowledged_at, created_at, updated_at, started_at, finished_at
    FROM agent.run
    WHERE workspace_id = :workspace_id AND requested_by = :requested_by
      AND (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
      AND (CAST(:kind AS text) IS NULL OR kind = CAST(:kind AS text))
      AND (CAST(:prompt_id AS text) IS NULL OR prompt_id = CAST(:prompt_id AS text))
      AND (CAST(:version_id AS text) IS NULL OR version_id = CAST(:version_id AS text))
    ORDER BY updated_at DESC, id DESC
    LIMIT :limit
""")
READ_ACTIVE_IMPROVEMENT = text("""
    SELECT id FROM agent.run
    WHERE workspace_id = :workspace_id AND requested_by = :requested_by
      AND prompt_id = :prompt_id AND kind = 'improvement'
      AND status IN ('queued', 'running')
    ORDER BY created_at DESC LIMIT 1
""")
LOCK_IMPROVEMENT_SCOPE = text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))")
READ_NODES = text("""
    SELECT id, sequence, capability, kind, status, evidence_refs,
           progress_current, progress_total, progress_unit, started_at, finished_at
    FROM agent.node
    WHERE workspace_id = :workspace_id AND run_id = :run_id
    ORDER BY sequence
""")
READ_EDGES = text("""
    SELECT source_node_id, target_node_id
    FROM agent.edge
    WHERE workspace_id = :workspace_id AND run_id = :run_id
    ORDER BY source_node_id, target_node_id
""")
ACKNOWLEDGE = text("""
    UPDATE agent.run SET acknowledged_at = :now, updated_at = :now
    WHERE workspace_id = :workspace_id AND requested_by = :requested_by AND id = :run_id
    RETURNING id
""")
CLAIM_RUNS = text("""
    WITH candidates AS (
        SELECT id FROM agent.run
        WHERE workspace_id = :workspace_id
          AND status IN ('queued', 'running')
          AND plan_basis <> 'llm'
          AND (lease_until IS NULL OR lease_until < :now)
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT :limit
    )
    UPDATE agent.run r
       SET status = 'running', lease_owner = :worker_id, lease_until = :lease_until,
           started_at = coalesce(started_at, :now), updated_at = :now
      FROM candidates c
     WHERE r.id = c.id
    RETURNING r.id, r.kind, r.source_refs, r.prompt_id, r.version_id, r.requested_by
""")
UPDATE_RUN = text("""
    UPDATE agent.run
       SET status = :status, progress_current = :current, progress_total = :total,
           progress_unit = :unit, result_actions = CAST(:actions AS jsonb),
           lease_owner = NULL, lease_until = NULL,
           updated_at = CAST(:now AS timestamptz),
           finished_at = CASE
               WHEN :terminal THEN CAST(:now AS timestamptz)
               ELSE NULL
           END
     WHERE workspace_id = :workspace_id AND id = :run_id
""")
UPDATE_NODE = text("""
    UPDATE agent.node
       SET status = :status, evidence_refs = CAST(:evidence_refs AS jsonb),
           progress_current = :current, progress_total = :total, progress_unit = :unit,
           started_at = CASE
               WHEN :status <> 'pending' THEN coalesce(started_at, CAST(:now AS timestamptz))
               ELSE started_at
           END,
           finished_at = CASE
               WHEN :terminal THEN CAST(:now AS timestamptz)
               ELSE NULL
           END
     WHERE workspace_id = :workspace_id AND run_id = :run_id AND sequence = :sequence
""")
FINALIZE_SOURCE_NODES = text("""
    UPDATE agent.node
       SET status = CASE
               WHEN kind = 'human_decision' THEN 'waiting_for_user'
               WHEN :run_status = 'failed' THEN 'failed'
               WHEN :run_status = 'warning'
                    AND capability IN ('evaluation_assertions', 'duplicate_adjudication')
                   THEN 'warning'
               ELSE 'succeeded'
           END,
           evidence_refs = CASE
               WHEN kind = 'human_decision' THEN evidence_refs
               ELSE CAST(:evidence_refs AS jsonb)
           END,
           progress_current = CASE
               WHEN kind = 'human_decision' THEN NULL
               ELSE CAST(:current AS integer)
           END,
           progress_total = CASE
               WHEN kind = 'human_decision' THEN NULL
               ELSE CAST(:total AS integer)
           END,
           progress_unit = CASE
               WHEN kind = 'human_decision' THEN NULL
               ELSE CAST(:unit AS text)
           END,
           started_at = coalesce(started_at, CAST(:now AS timestamptz)),
           finished_at = CASE
               WHEN kind = 'human_decision' THEN NULL
               ELSE CAST(:now AS timestamptz)
           END
     WHERE workspace_id = :workspace_id AND run_id = :run_id
""")
FINISH_INLINE_RUN = text("""
    UPDATE agent.run
       SET status = :status, updated_at = CAST(:now AS timestamptz),
           started_at = coalesce(started_at, CAST(:now AS timestamptz)),
           finished_at = CASE
               WHEN :terminal THEN CAST(:now AS timestamptz)
               ELSE NULL
           END
     WHERE workspace_id = :workspace_id AND id = :run_id
""")
START_INLINE_RUN = text("""
    UPDATE agent.run
       SET status = 'running', updated_at = CAST(:now AS timestamptz),
           started_at = coalesce(started_at, CAST(:now AS timestamptz))
     WHERE workspace_id = :workspace_id AND id = :run_id AND status = 'queued'
""")
START_INLINE_NODE = text("""
    UPDATE agent.node
       SET status = 'running', started_at = coalesce(started_at, CAST(:now AS timestamptz))
     WHERE workspace_id = :workspace_id AND run_id = :run_id AND sequence = 0
""")
FINISH_INLINE_NODES = text("""
    UPDATE agent.node
       SET status = CASE
               WHEN kind = 'human_decision' AND :waiting THEN 'waiting_for_user'
               ELSE 'succeeded'
           END,
           evidence_refs = CAST(:evidence_refs AS jsonb),
           started_at = coalesce(started_at, CAST(:now AS timestamptz)),
           finished_at = CASE
               WHEN kind = 'human_decision' AND :waiting THEN NULL
               ELSE CAST(:now AS timestamptz)
           END
     WHERE workspace_id = :workspace_id AND run_id = :run_id
""")
FAIL_INLINE_NODES = text("""
    UPDATE agent.node
       SET status = CASE WHEN status = 'succeeded' THEN status ELSE 'failed' END,
           started_at = coalesce(started_at, CAST(:now AS timestamptz)),
           finished_at = CASE
               WHEN status = 'succeeded' THEN finished_at
               ELSE CAST(:now AS timestamptz)
           END
     WHERE workspace_id = :workspace_id AND run_id = :run_id
""")
FAIL_INLINE_RUN = text("""
    UPDATE agent.run
       SET status = 'failed', lease_owner = NULL, lease_until = NULL,
           updated_at = CAST(:now AS timestamptz),
           started_at = coalesce(started_at, CAST(:now AS timestamptz)),
           finished_at = CAST(:now AS timestamptz)
     WHERE workspace_id = :workspace_id AND id = :run_id
       AND status IN ('queued', 'running')
""")
IMPORT_PROGRESS = text("""
    SELECT count(*)::integer AS item_count,
           count(*) FILTER (WHERE state IN ('ready', 'committed', 'skipped', 'failed', 'needs_attention'))::integer AS finished_count,
           count(*) FILTER (WHERE state IN ('failed', 'needs_attention'))::integer AS warning_count
      FROM ingestion.import_item
     WHERE batch_id = :batch_id
""")


def _run_read(row: Any) -> dict[str, Any]:
    return {
        "run_id": row["id"], "kind": row["kind"], "plan_basis": row["plan_basis"],
        "status": row["status"], "prompt_id": row["prompt_id"],
        "version_id": row["version_id"], "source_refs": list(row["source_refs"]),
        "result_actions": list(row["result_actions"]),
        "progress_current": row["progress_current"], "progress_total": row["progress_total"],
        "progress_unit": row["progress_unit"], "acknowledged_at": row["acknowledged_at"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "started_at": row["started_at"], "finished_at": row["finished_at"],
    }


async def create_run(
    db: AsyncSession, *, workspace_id: str, requested_by: str, kind: RunKind,
    plan_basis: PlanBasis, idempotency_key: str, prompt_id: str | None = None,
    version_id: str | None = None, source_refs: tuple[str, ...] = (),
    result_actions: tuple[dict[str, str], ...] = (), now: datetime | None = None,
) -> str:
    created_at = now or datetime.now(UTC)
    run_id = f"arn_{ULID()}"
    inserted = (await db.execute(INSERT_RUN, {
        "id": run_id, "workspace_id": workspace_id, "requested_by": requested_by,
        "kind": kind.value, "plan_basis": plan_basis.value, "prompt_id": prompt_id,
        "version_id": version_id, "source_refs": json.dumps(source_refs),
        "result_actions": json.dumps(result_actions), "idempotency_key": idempotency_key,
        "now": created_at,
    })).scalar_one_or_none()
    if inserted is None:
        return str((await db.execute(READ_BY_KEY, {
            "workspace_id": workspace_id, "idempotency_key": idempotency_key,
        })).scalar_one())

    node_ids: list[str] = []
    for sequence, planned in enumerate(PLAN_CATALOGUE[kind]):
        node_id = f"nod_{ULID()}"
        node_ids.append(node_id)
        await db.execute(INSERT_NODE, {
            "run_id": run_id, "workspace_id": workspace_id, "id": node_id,
            "sequence": sequence, "capability": planned.capability,
            "kind": planned.kind.value, "idempotency_key": f"{idempotency_key}:{sequence}",
        })
    for source, target in zip(node_ids, node_ids[1:], strict=False):
        await db.execute(INSERT_EDGE, {
            "run_id": run_id, "workspace_id": workspace_id,
            "source": source, "target": target,
        })
    return run_id


async def read_run(db: AsyncSession, *, workspace_id: str, requested_by: str, run_id: str) -> dict[str, Any] | None:
    row = (await db.execute(READ_RUN, {
        "workspace_id": workspace_id, "requested_by": requested_by, "run_id": run_id,
    })).mappings().first()
    if row is None:
        return None
    result = _run_read(row)
    result["nodes"] = [dict(item) for item in (await db.execute(READ_NODES, {
        "workspace_id": workspace_id, "run_id": run_id,
    })).mappings().all()]
    result["edges"] = [
        {"source": item["source_node_id"], "target": item["target_node_id"]}
        for item in (await db.execute(READ_EDGES, {
            "workspace_id": workspace_id, "run_id": run_id,
        })).mappings().all()
    ]
    return result


async def list_runs(
    db: AsyncSession, *, workspace_id: str, requested_by: str,
    status: RunStatus | None, limit: int, kind: RunKind | None = None,
    prompt_id: str | None = None, version_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = (await db.execute(LIST_RUNS, {
        "workspace_id": workspace_id, "requested_by": requested_by,
        "status": None if status is None else status.value, "limit": limit,
        "kind": None if kind is None else kind.value,
        "prompt_id": prompt_id, "version_id": version_id,
    })).mappings().all()
    return [_run_read(row) for row in rows]


async def active_improvement_run(
    db: AsyncSession, *, workspace_id: str, requested_by: str, prompt_id: str
) -> str | None:
    value = await db.scalar(READ_ACTIVE_IMPROVEMENT, {
        "workspace_id": workspace_id, "requested_by": requested_by, "prompt_id": prompt_id,
    })
    return None if value is None else str(value)


async def lock_improvement_scope(
    db: AsyncSession, *, workspace_id: str, requested_by: str, prompt_id: str
) -> None:
    await db.execute(LOCK_IMPROVEMENT_SCOPE, {
        "scope": f"{workspace_id}:{requested_by}:{prompt_id}:manual-improvement",
    })


async def acknowledge(db: AsyncSession, *, workspace_id: str, requested_by: str, run_id: str) -> bool:
    return (await db.execute(ACKNOWLEDGE, {
        "workspace_id": workspace_id, "requested_by": requested_by,
        "run_id": run_id, "now": datetime.now(UTC),
    })).scalar_one_or_none() is not None


async def finish_inline_run(
    db: AsyncSession, *, workspace_id: str, run_id: str,
    evidence_refs: tuple[str, ...], waiting_for_user: bool,
) -> None:
    now = datetime.now(UTC)
    await db.execute(FINISH_INLINE_NODES, {
        "workspace_id": workspace_id, "run_id": run_id,
        "evidence_refs": json.dumps(evidence_refs), "waiting": waiting_for_user,
        "now": now,
    })
    await db.execute(FINISH_INLINE_RUN, {
        "workspace_id": workspace_id, "run_id": run_id,
        "status": RunStatus.WAITING_FOR_USER.value if waiting_for_user else RunStatus.SUCCEEDED.value,
        "terminal": not waiting_for_user, "now": now,
    })


async def start_inline_run(
    db: AsyncSession, *, workspace_id: str, run_id: str
) -> None:
    now = datetime.now(UTC)
    await db.execute(START_INLINE_RUN, {
        "workspace_id": workspace_id,
        "run_id": run_id,
        "now": now,
    })
    await db.execute(START_INLINE_NODE, {
        "workspace_id": workspace_id,
        "run_id": run_id,
        "now": now,
    })


async def fail_inline_run(
    db: AsyncSession, *, workspace_id: str, run_id: str
) -> None:
    now = datetime.now(UTC)
    await db.execute(FAIL_INLINE_NODES, {
        "workspace_id": workspace_id,
        "run_id": run_id,
        "now": now,
    })
    await db.execute(FAIL_INLINE_RUN, {
        "workspace_id": workspace_id,
        "run_id": run_id,
        "now": now,
    })


#: One plan's step count, from the catalogue the nodes were written from.
#: Hardcoding the integer is how a sixth node ships with a progress bar that
#: stops at five — the drift path's totals and the eval path's are the same
#: number because the plan is the same shape.
IMPROVEMENT_STEPS = len(PLAN_CATALOGUE[RunKind.IMPROVEMENT])

#: The sequence of the draft node — the one step the drift path never runs.
#: `skipped` rather than `succeeded`: a reviewer reading the plan must be able
#: to tell "the drafter ran" from "this path has no drafter".
IMPROVEMENT_DRAFT_SEQUENCE = next(
    sequence
    for sequence, node in enumerate(PLAN_CATALOGUE[RunKind.IMPROVEMENT])
    if node.capability == "improvement_draft"
)


async def start_improvement_execution(
    db: AsyncSession, *, workspace_id: str, run_id: str
) -> None:
    await db.execute(UPDATE_NODE, {
        "workspace_id": workspace_id, "run_id": run_id, "sequence": 0,
        "status": "running", "evidence_refs": "[]", "current": 0,
        "total": IMPROVEMENT_STEPS, "unit": "steps", "terminal": False, "now": datetime.now(UTC),
    })


async def advance_improvement_execution(
    db: AsyncSession, *, workspace_id: str, run_id: str, sequence: int
) -> None:
    now = datetime.now(UTC)
    for current in range(sequence + 1):
        await db.execute(UPDATE_NODE, {
            "workspace_id": workspace_id, "run_id": run_id, "sequence": current,
            "status": "running" if current == sequence else "succeeded",
            "evidence_refs": "[]", "current": current,
            "total": IMPROVEMENT_STEPS, "unit": "steps", "terminal": current < sequence, "now": now,
        })


async def finish_improvement_execution(
    db: AsyncSession, *, workspace_id: str, run_id: str,
    action: dict[str, str], source_refs: tuple[str, ...],
    drafted: bool = False,
) -> None:
    now = datetime.now(UTC)
    kind = action.get("kind", "no_change")
    waiting = kind == "open_improvement"
    limited = kind == "limited_evidence"
    run_status = RunStatus.WAITING_FOR_USER if waiting else (RunStatus.WARNING if limited else RunStatus.SUCCEEDED)
    for sequence in range(IMPROVEMENT_STEPS):
        human = sequence == IMPROVEMENT_STEPS - 1
        if sequence == IMPROVEMENT_DRAFT_SEQUENCE and not drafted:
            node_status = "skipped"
        elif human:
            node_status = "waiting_for_user" if waiting else "skipped"
        else:
            node_status = "succeeded"
        await db.execute(UPDATE_NODE, {
            "workspace_id": workspace_id, "run_id": run_id, "sequence": sequence,
            "status": node_status, "evidence_refs": json.dumps(source_refs),
            "current": sequence + 1 if not human else None,
            "total": IMPROVEMENT_STEPS if not human else None, "unit": "steps" if not human else None,
            "terminal": node_status != "waiting_for_user", "now": now,
        })
    await db.execute(UPDATE_RUN, {
        "workspace_id": workspace_id, "run_id": run_id, "status": run_status.value,
        "current": IMPROVEMENT_STEPS, "total": IMPROVEMENT_STEPS, "unit": "steps",
        "actions": json.dumps([action]), "terminal": not waiting, "now": now,
    })


async def claim_runs(db: AsyncSession, *, workspace_id: str, worker_id: str, limit: int = 20) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    return [dict(row) for row in (await db.execute(CLAIM_RUNS, {
        "workspace_id": workspace_id, "worker_id": worker_id, "limit": limit,
        "now": now, "lease_until": now + timedelta(minutes=2),
    })).mappings().all()]


async def sync_claimed_run(db: AsyncSession, *, workspace_id: str, claimed: dict[str, Any]) -> None:
    run_id = str(claimed["id"])
    refs = tuple(str(ref) for ref in claimed["source_refs"])
    now = datetime.now(UTC)
    status = RunStatus.WAITING_FOR_USER
    current: int | None = None
    total: int | None = None
    unit: str | None = None
    actions: list[dict[str, str]] = []
    terminal = False

    if claimed["kind"] == RunKind.EVALUATION.value:
        eval_ids = [ref.removeprefix("eval:") for ref in refs if ref.startswith("eval:")]
        if eval_ids:
            progress = await run_progress(db, eval_ids)
            current, total, unit = progress.completed_cases, progress.total_cases, "cases"
            if progress.interrupted:
                status, terminal = RunStatus.FAILED, True
            elif progress.run_count and progress.finished_count == progress.run_count:
                status = RunStatus.WARNING if progress.fail_count or progress.error_count else RunStatus.SUCCEEDED
                terminal = True
                actions = [{"kind": "open_evaluation", "run_id": eval_ids[0]}]
            else:
                status = RunStatus.RUNNING
    elif claimed["kind"] == RunKind.IMPORT.value:
        batch_refs = [ref.removeprefix("import:") for ref in refs if ref.startswith("import:")]
        if batch_refs:
            progress = (await db.execute(IMPORT_PROGRESS, {"batch_id": batch_refs[0]})).mappings().one()
            current, total, unit = progress["finished_count"], progress["item_count"], "items"
            if total and current == total:
                status = RunStatus.WARNING if progress["warning_count"] else RunStatus.WAITING_FOR_USER
                actions = [{"kind": "review_import", "batch_id": batch_refs[0]}]
            else:
                status = RunStatus.RUNNING

    await db.execute(UPDATE_RUN, {
        "workspace_id": workspace_id, "run_id": run_id, "status": status.value,
        "current": current, "total": total, "unit": unit,
        "actions": json.dumps(actions), "terminal": terminal, "now": now,
    })
    if terminal or status is RunStatus.WAITING_FOR_USER:
        await db.execute(FINALIZE_SOURCE_NODES, {
            "workspace_id": workspace_id,
            "run_id": run_id,
            "run_status": status.value,
            "evidence_refs": json.dumps(refs),
            "current": current,
            "total": total,
            "unit": unit,
            "now": now,
        })
        return
    node_status = "succeeded" if terminal else ("running" if status is RunStatus.RUNNING else "waiting_for_user")
    await db.execute(UPDATE_NODE, {
        "workspace_id": workspace_id, "run_id": run_id, "sequence": 0,
        "status": node_status, "evidence_refs": json.dumps(refs),
        "current": current, "total": total, "unit": unit,
        "terminal": terminal, "now": now,
    })

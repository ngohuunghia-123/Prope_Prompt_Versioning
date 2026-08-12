from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.evaluation.assertions import parse_assertions
from prope.evaluation.domain import (
    AssertionOutcome,
    AssertionType,
    CaseOutcome,
    CaseResultRow,
    CaseRow,
    OutputModality,
    RefusalReason,
    RunRole,
    RunRow,
    RunStatus,
    SuiteRow,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "count_queued_runs",
    "find_baseline_run",
    "latest_completed_run",
    "list_case_results",
    "list_cases",
    "list_current_suites",
    "list_runs_for_version",
    "list_stalled_runs",
    "list_suite_versions",
    "load_current_suite",
    "load_run",
    "load_suite",
    "next_suite_version",
]

DEFAULT_LIMIT = 50

MAX_LIMIT = 200

LOAD_SUITE = text(
    """
    SELECT id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  id = :suite_id
    """
)

LOAD_CURRENT_SUITE = text(
    """
    SELECT id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id AND name = :name
    ORDER  BY suite_version DESC
    LIMIT  1
    """
)

LIST_CURRENT_SUITES = text(
    """
    SELECT DISTINCT ON (name)
           id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id
    ORDER  BY name, suite_version DESC
    """
)

LIST_SUITE_VERSIONS = text(
    """
    SELECT id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id AND name = :name
    ORDER  BY suite_version DESC
    LIMIT  :limit
    """
)

NEXT_SUITE_VERSION = text(
    """
    SELECT coalesce(max(suite_version), 0) + 1
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id AND name = :name
    """
)

LIST_CASES = text(
    """
    SELECT id, workspace_id, suite_id, ordinal, name, input_messages,
           input_variables, assertions, created_at
    FROM   evaluation.eval_case
    WHERE  suite_id = :suite_id
    ORDER  BY ordinal
    """
)

LOAD_RUN = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, suite_id, role, status,
           refused_reason, started_at, finished_at, pass_count, fail_count,
           error_count, input_tokens, output_tokens, cost_amount, cost_currency,
           priced_at, started_by
    FROM   evaluation.eval_run
    WHERE  id = :run_id
    """
)

LIST_RUNS_FOR_VERSION = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, suite_id, role, status,
           refused_reason, started_at, finished_at, pass_count, fail_count,
           error_count, input_tokens, output_tokens, cost_amount, cost_currency,
           priced_at, started_by
    FROM   evaluation.eval_run
    WHERE  prompt_id = :prompt_id AND version_id = :version_id AND role = 'candidate'
    ORDER  BY id DESC
    """
)

LATEST_COMPLETED_RUN = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, suite_id, role, status,
           refused_reason, started_at, finished_at, pass_count, fail_count,
           error_count, input_tokens, output_tokens, cost_amount, cost_currency,
           priced_at, started_by
    FROM   evaluation.eval_run
    WHERE  version_id = :version_id AND suite_id = :suite_id AND status = 'completed'
    ORDER  BY id DESC
    LIMIT  1
    """
)

LIST_CASE_RESULTS = text(
    """
    SELECT id, workspace_id, run_id, case_id, outcome, assertion_results,
           output_content, latency_ms, input_tokens, output_tokens, error_code,
           attempt_count, created_at
    FROM   evaluation.case_result
    WHERE  run_id = :run_id
    ORDER  BY created_at, id
    """
)

COUNT_QUEUED_RUNS = text("SELECT count(*) FROM evaluation.eval_run WHERE status = 'queued'")

LIST_STALLED_RUNS = text(
    """
    SELECT r.id
    FROM   evaluation.eval_run AS r
    WHERE  r.status = 'running'
      AND  coalesce(
               (SELECT max(c.created_at) FROM evaluation.case_result AS c WHERE c.run_id = r.id),
               r.started_at
           ) < :cutoff
    ORDER  BY r.id
    """
)


def _suite(row: Any) -> SuiteRow:
    return SuiteRow(
        id=row.id,
        workspace_id=row.workspace_id,
        prompt_id=row.prompt_id,
        name=row.name,
        suite_version=row.suite_version,
        output_modality=OutputModality(row.output_modality),
        case_count=row.case_count,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _case(row: Any) -> CaseRow:
    return CaseRow(
        id=row.id,
        workspace_id=row.workspace_id,
        suite_id=row.suite_id,
        ordinal=row.ordinal,
        name=row.name,
        input_messages=tuple(row.input_messages),
        input_variables=dict(row.input_variables),
        assertions=parse_assertions(row.assertions),
        created_at=row.created_at,
    )


def _run(row: Any) -> RunRow:
    return RunRow(
        id=row.id,
        workspace_id=row.workspace_id,
        prompt_id=row.prompt_id,
        version_id=row.version_id,
        suite_id=row.suite_id,
        role=RunRole(row.role),
        status=RunStatus(row.status),
        refused_reason=None if row.refused_reason is None else RefusalReason(row.refused_reason),
        started_at=row.started_at,
        finished_at=row.finished_at,
        pass_count=row.pass_count,
        fail_count=row.fail_count,
        error_count=row.error_count,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cost_amount=row.cost_amount,
        cost_currency=row.cost_currency,
        priced_at=row.priced_at,
        started_by=row.started_by,
    )


def _case_result(row: Any) -> CaseResultRow:
    return CaseResultRow(
        id=row.id,
        workspace_id=row.workspace_id,
        run_id=row.run_id,
        case_id=row.case_id,
        outcome=CaseOutcome(row.outcome),
        assertion_results=tuple(
            AssertionOutcome(
                type=AssertionType(entry["type"]),
                passed=bool(entry["passed"]),
                detail=entry.get("detail"),
            )
            for entry in row.assertion_results
        ),
        output_content=row.output_content,
        latency_ms=row.latency_ms,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        error_code=row.error_code,
        attempt_count=row.attempt_count,
        created_at=row.created_at,
    )


async def load_suite(db: AsyncSession, suite_id: str) -> SuiteRow | None:
    row = (await db.execute(LOAD_SUITE, {"suite_id": suite_id})).first()
    return None if row is None else _suite(row)


async def load_current_suite(db: AsyncSession, prompt_id: str, name: str) -> SuiteRow | None:
    row = (await db.execute(LOAD_CURRENT_SUITE, {"prompt_id": prompt_id, "name": name})).first()
    return None if row is None else _suite(row)


async def list_current_suites(db: AsyncSession, prompt_id: str) -> tuple[SuiteRow, ...]:
    rows = (await db.execute(LIST_CURRENT_SUITES, {"prompt_id": prompt_id})).all()
    return tuple(_suite(row) for row in rows)


async def list_suite_versions(
    db: AsyncSession, prompt_id: str, name: str, *, limit: int = DEFAULT_LIMIT
) -> tuple[SuiteRow, ...]:
    rows = (
        await db.execute(
            LIST_SUITE_VERSIONS, {"prompt_id": prompt_id, "name": name, "limit": limit}
        )
    ).all()
    return tuple(_suite(row) for row in rows)


async def next_suite_version(db: AsyncSession, prompt_id: str, name: str) -> int:
    return int(await db.scalar(NEXT_SUITE_VERSION, {"prompt_id": prompt_id, "name": name}) or 1)


async def list_cases(db: AsyncSession, suite_id: str) -> tuple[CaseRow, ...]:
    rows = (await db.execute(LIST_CASES, {"suite_id": suite_id})).all()
    return tuple(_case(row) for row in rows)


async def load_run(db: AsyncSession, run_id: str) -> RunRow | None:
    row = (await db.execute(LOAD_RUN, {"run_id": run_id})).first()
    return None if row is None else _run(row)


async def list_runs_for_version(
    db: AsyncSession, prompt_id: str, version_id: str
) -> tuple[RunRow, ...]:
    rows = (
        await db.execute(
            LIST_RUNS_FOR_VERSION, {"prompt_id": prompt_id, "version_id": version_id}
        )
    ).all()
    return tuple(_run(row) for row in rows)


async def latest_completed_run(db: AsyncSession, version_id: str, suite_id: str) -> RunRow | None:
    row = (
        await db.execute(LATEST_COMPLETED_RUN, {"version_id": version_id, "suite_id": suite_id})
    ).first()
    return None if row is None else _run(row)


async def find_baseline_run(
    db: AsyncSession, released_version_id: str | None, suite_id: str
) -> RunRow | None:
    if released_version_id is None:
        return None
    return await latest_completed_run(db, released_version_id, suite_id)


async def list_case_results(db: AsyncSession, run_id: str) -> tuple[CaseResultRow, ...]:
    rows = (await db.execute(LIST_CASE_RESULTS, {"run_id": run_id})).all()
    return tuple(_case_result(row) for row in rows)


async def count_queued_runs(db: AsyncSession) -> int:
    return int(await db.scalar(COUNT_QUEUED_RUNS) or 0)


async def list_stalled_runs(db: AsyncSession, cutoff: datetime) -> tuple[str, ...]:
    return tuple((await db.execute(LIST_STALLED_RUNS, {"cutoff": cutoff})).scalars().all())

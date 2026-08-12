import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.evaluation import events, repository
from prope.evaluation.assertions import compile_assertions
from prope.evaluation.domain import (
    MAX_CASES_PER_SUITE,
    AssertionOutcome,
    AssertionPatternInvalid,
    CaseDraft,
    CaseOutcome,
    OutputModality,
    RefusalReason,
    RunRole,
    SuiteRow,
)

log = structlog.get_logger(__name__)

__all__ = [
    "CASE_ID_PREFIX",
    "CASE_RESULT_ID_PREFIX",
    "RUN_ID_PREFIX",
    "SUITE_ID_PREFIX",
    "create_runs",
    "mark_completed",
    "mark_interrupted",
    "mark_refused",
    "record_case_result",
    "stamp_case_count",
    "stamp_price",
    "write_suite_version",
]

SUITE_ID_PREFIX = "evs_"

CASE_ID_PREFIX = "evc_"

RUN_ID_PREFIX = "evr_"

CASE_RESULT_ID_PREFIX = "evcr_"

INSERT_SUITE = text(
    """
    INSERT INTO evaluation.eval_suite (
        id, workspace_id, prompt_id, name, suite_version, output_modality,
        case_count, created_by, created_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :name, :suite_version, :output_modality,
        :case_count, :created_by, :now
    )
    """
)

INSERT_CASE = text(
    """
    INSERT INTO evaluation.eval_case (
        id, workspace_id, suite_id, ordinal, name, input_messages,
        input_variables, assertions, created_at
    ) VALUES (
        :id, :workspace_id, :suite_id, :ordinal, :name,
        CAST(:input_messages AS jsonb), CAST(:input_variables AS jsonb),
        CAST(:assertions AS jsonb), :now
    )
    """
)

INSERT_RUN = text(
    """
    INSERT INTO evaluation.eval_run (
        id, workspace_id, prompt_id, version_id, suite_id, role, status, started_by
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, :suite_id, :role, 'queued', :started_by
    )
    """
)

INSERT_CASE_RESULT = text(
    """
    INSERT INTO evaluation.case_result (
        id, workspace_id, run_id, case_id, outcome, assertion_results,
        output_content, latency_ms, input_tokens, output_tokens, error_code,
        attempt_count, created_at
    ) VALUES (
        :id, :workspace_id, :run_id, :case_id, :outcome,
        CAST(:assertion_results AS jsonb), :output_content, :latency_ms,
        :input_tokens, :output_tokens, :error_code, :attempt_count, :now
    )
    """
)

REFUSE_RUN = text(
    """
    UPDATE evaluation.eval_run
       SET status = 'refused', refused_reason = :reason, finished_at = :now
     WHERE id = :run_id AND status IN ('queued', 'running')
    """
)

COMPLETE_RUN = text(
    """
    UPDATE evaluation.eval_run
       SET status = 'completed',
           finished_at = :now,
           pass_count = :pass_count,
           fail_count = :fail_count,
           error_count = :error_count,
           input_tokens = :input_tokens,
           output_tokens = :output_tokens,
           cost_amount = :cost_amount,
           cost_currency = :cost_currency,
           priced_at = :priced_at
     WHERE id = :run_id AND status = 'running'
    """
)

INTERRUPT_RUN = text(
    """
    UPDATE evaluation.eval_run
       SET status = 'interrupted', finished_at = :now
     WHERE id = :run_id AND status = 'running'
    """
)

STAMP_PRICE = text(
    """
    UPDATE evaluation.eval_run
       SET cost_amount = :cost_amount,
           cost_currency = :cost_currency,
           priced_at = :priced_at
     WHERE id = :run_id
    """
)

STAMP_CASE_COUNT = text(
    "UPDATE evaluation.eval_suite SET case_count = :case_count WHERE id = :suite_id"
)


def _new_id(prefix: str) -> str:
    return f"{prefix}{ULID()}"


async def write_suite_version(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    name: str,
    output_modality: OutputModality,
    cases: Sequence[CaseDraft],
    now: datetime,
) -> SuiteRow:
    if len(cases) > MAX_CASES_PER_SUITE:
        raise AssertionPatternInvalid(
            len(cases), f"a suite holds at most {MAX_CASES_PER_SUITE} cases"
        )

    suite_version = await repository.next_suite_version(db, prompt_id, name)
    suite_id = _new_id(SUITE_ID_PREFIX)

    await db.execute(
        INSERT_SUITE,
        {
            "id": suite_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "name": name,
            "suite_version": suite_version,
            "output_modality": output_modality.value,
            "case_count": len(cases),
            "created_by": actor_id,
            "now": now,
        },
    )

    for ordinal, draft in enumerate(cases, start=1):
        compiled = compile_assertions(draft.assertions, output_modality, ordinal)
        await db.execute(
            INSERT_CASE,
            {
                "id": _new_id(CASE_ID_PREFIX),
                "workspace_id": workspace_id,
                "suite_id": suite_id,
                "ordinal": ordinal,
                "name": draft.name,
                "input_messages": json.dumps(list(draft.input_messages)),
                "input_variables": json.dumps(dict(draft.input_variables)),
                "assertions": json.dumps([spec.as_json() for spec in compiled]),
                "now": now,
            },
        )

    await events.eval_suite_updated(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        suite_id=suite_id,
        occurred_at=now,
    )

    log.info(
        "evaluation.suite_written",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        suite_id=suite_id,
        suite_name=name,
        suite_version=suite_version,
    )

    return SuiteRow(
        id=suite_id,
        workspace_id=workspace_id,
        prompt_id=prompt_id,
        name=name,
        suite_version=suite_version,
        output_modality=output_modality,
        case_count=len(cases),
        created_by=actor_id,
        created_at=now,
    )


async def create_runs(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    suite_ids: Sequence[str],
    role: RunRole,
    now: datetime,
) -> tuple[str, ...]:
    created: list[str] = []

    for suite_id in suite_ids:
        run_id = _new_id(RUN_ID_PREFIX)
        await db.execute(
            INSERT_RUN,
            {
                "id": run_id,
                "workspace_id": workspace_id,
                "prompt_id": prompt_id,
                "version_id": version_id,
                "suite_id": suite_id,
                "role": role.value,
                "started_by": actor_id,
            },
        )
        await events.eval_run_started(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            run_id=run_id,
            occurred_at=now,
        )
        created.append(run_id)

    log.info(
        "evaluation.runs_created",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=version_id,
        role=role.value,
    )

    return tuple(created)


async def record_case_result(
    db: AsyncSession,
    *,
    workspace_id: str,
    run_id: str,
    case_id: str,
    outcome: CaseOutcome,
    assertion_results: Sequence[AssertionOutcome],
    output_content: str | None,
    latency_ms: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    error_code: str | None,
    attempt_count: int,
    now: datetime,
) -> str:
    result_id = _new_id(CASE_RESULT_ID_PREFIX)
    await db.execute(
        INSERT_CASE_RESULT,
        {
            "id": result_id,
            "workspace_id": workspace_id,
            "run_id": run_id,
            "case_id": case_id,
            "outcome": outcome.value,
            "assertion_results": json.dumps([entry.as_json() for entry in assertion_results]),
            "output_content": output_content,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error_code": error_code,
            "attempt_count": attempt_count,
            "now": now,
        },
    )
    return result_id


async def mark_refused(
    db: AsyncSession, *, run_id: str, reason: RefusalReason, now: datetime
) -> None:
    await db.execute(REFUSE_RUN, {"run_id": run_id, "reason": reason.value, "now": now})


async def mark_completed(
    db: AsyncSession,
    *,
    run_id: str,
    pass_count: int,
    fail_count: int,
    error_count: int,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_amount: Decimal | None,
    cost_currency: str | None,
    priced_at: datetime | None,
    now: datetime,
) -> None:
    await db.execute(
        COMPLETE_RUN,
        {
            "run_id": run_id,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "error_count": error_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_amount": cost_amount,
            "cost_currency": cost_currency,
            "priced_at": priced_at,
            "now": now,
        },
    )


async def mark_interrupted(db: AsyncSession, *, run_id: str, now: datetime) -> bool:
    result = await db.execute(INTERRUPT_RUN, {"run_id": run_id, "now": now})
    return bool(result.rowcount)


async def stamp_case_count(db: AsyncSession, *, suite_id: str, case_count: int) -> None:
    await db.execute(STAMP_CASE_COUNT, {"suite_id": suite_id, "case_count": case_count})


async def stamp_price(
    db: AsyncSession,
    *,
    run_id: str,
    cost_amount: Decimal | None,
    cost_currency: str | None,
    priced_at: datetime | None,
) -> None:
    await db.execute(
        STAMP_PRICE,
        {
            "run_id": run_id,
            "cost_amount": cost_amount,
            "cost_currency": cost_currency,
            "priced_at": priced_at,
        },
    )

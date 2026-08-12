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
from prope.call_ledger.seams import (
    EvalUsageRow,
    check_spend_ceiling,
    get_run_totals,
    price_usage,
)
from prope.db.session import workspace_transaction
from prope.evaluation import commands, events, repository
from prope.evaluation.assertions import (
    AssertionTimeout,
    AssertionUnevaluable,
    CaseObservation,
    check_modality,
    evaluate_all,
)
from prope.evaluation.claim import claim_next_run
from prope.evaluation.domain import (
    CASE_DEADLINE_MS,
    MAX_CONCURRENT_RUNS,
    MAX_TRANSPORT_RETRIES,
    PER_RUN_CONCURRENCY,
    AssertionOutcome,
    CaseErrorCode,
    CaseOutcome,
    CaseRow,
    ClaimedRun,
    ModalityMismatch,
    OutputModality,
    RefusalReason,
    RunStatus,
)
from prope.evaluation.observability import (
    case_duration_seconds,
    case_error_total,
    modality_mismatch_total,
    run_duration_seconds,
    run_total,
    unpriced_run_total,
)
from prope.prompt_registry.domain import RevisionRead
from prope.prompt_registry.seams import get_revision
from prope.provider_access.domain import DispatchError, DispatchResult, Priority
from prope.provider_access.seams import dispatch

log = structlog.get_logger(__name__)

__all__ = [
    "CALL_ID_PREFIX",
    "CaseAttempt",
    "execute_run",
    "response_content",
    "run_claimed_batch",
]

CALL_ID_PREFIX = "cal_"

RETRY_BACKOFF_SECONDS = (0.5, 2.0)

Dispatcher = Callable[..., Awaitable[DispatchResult | DispatchError]]


@dataclass(frozen=True, slots=True)
class CaseAttempt:
    case_id: str
    outcome: CaseOutcome
    assertion_results: tuple[AssertionOutcome, ...]
    output_content: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None
    attempt_count: int
    provider_config_id: str | None
    upstream_model: str | None
    dispatched: bool


def _utc_now() -> datetime:
    return datetime.now(UTC)


def response_content(response: Mapping[str, Any] | None) -> str | None:
    if not response:
        return None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


async def _run_case(
    sessionmaker: async_sessionmaker[AsyncSession],
    case: CaseRow,
    revision: RevisionRead,
    *,
    workspace_id: str,
    modality: OutputModality,
    dispatcher: Dispatcher,
) -> CaseAttempt:
    started = time.perf_counter()
    attempt = 0

    try:
        while True:
            attempt += 1
            call_started = time.perf_counter()
            result = await dispatcher(
                sessionmaker,
                workspace_id=workspace_id,
                provider_config_id=revision.provider_config_id,
                upstream_model=revision.upstream_model,
                parameters=revision.parameters,
                messages=list(case.input_messages),
                deadline_ms=CASE_DEADLINE_MS,
                priority=Priority.BATCH,
            )
            latency_ms = int((time.perf_counter() - call_started) * 1000)

            if isinstance(result, DispatchError):
                if result.retryable and attempt <= MAX_TRANSPORT_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])
                    continue

                case_error_total.labels(error_code=result.error_class.value).inc()
                return CaseAttempt(
                    case_id=case.id,
                    outcome=CaseOutcome.ERROR,
                    assertion_results=(),
                    output_content=None,
                    latency_ms=latency_ms,
                    input_tokens=None if result.usage is None else result.usage.input_tokens,
                    output_tokens=None if result.usage is None else result.usage.output_tokens,
                    error_code=result.error_class.value,
                    attempt_count=attempt,
                    provider_config_id=revision.provider_config_id,
                    upstream_model=revision.upstream_model,
                    dispatched=True,
                )

            content = response_content(result.response)
            usage = result.usage
            observation = CaseObservation(content=content, latency_ms=latency_ms, cost=None)

            try:
                outcomes = evaluate_all(case.assertions, observation, modality)
            except (AssertionTimeout, AssertionUnevaluable) as error:
                case_error_total.labels(error_code=error.error_code.value).inc()
                return CaseAttempt(
                    case_id=case.id,
                    outcome=CaseOutcome.ERROR,
                    assertion_results=(),
                    output_content=content,
                    latency_ms=latency_ms,
                    input_tokens=None if usage is None else usage.input_tokens,
                    output_tokens=None if usage is None else usage.output_tokens,
                    error_code=error.error_code.value,
                    attempt_count=attempt,
                    provider_config_id=revision.provider_config_id,
                    upstream_model=revision.upstream_model,
                    dispatched=True,
                )

            passed = all(entry.passed for entry in outcomes)
            return CaseAttempt(
                case_id=case.id,
                outcome=CaseOutcome.PASS if passed else CaseOutcome.FAIL,
                assertion_results=outcomes,
                output_content=content,
                latency_ms=latency_ms,
                input_tokens=None if usage is None else usage.input_tokens,
                output_tokens=None if usage is None else usage.output_tokens,
                error_code=None,
                attempt_count=attempt,
                provider_config_id=revision.provider_config_id,
                upstream_model=revision.upstream_model,
                dispatched=True,
            )
    finally:
        case_duration_seconds.observe(time.perf_counter() - started)


def _unbindable(case: CaseRow, revision: RevisionRead) -> CaseAttempt:
    case_error_total.labels(error_code=CaseErrorCode.DISPATCH_FAILED.value).inc()
    return CaseAttempt(
        case_id=case.id,
        outcome=CaseOutcome.ERROR,
        assertion_results=(),
        output_content=None,
        latency_ms=None,
        input_tokens=None,
        output_tokens=None,
        error_code=CaseErrorCode.DISPATCH_FAILED.value,
        attempt_count=1,
        provider_config_id=revision.provider_config_id,
        upstream_model=revision.upstream_model,
        dispatched=False,
    )


def _usage_rows(
    attempts: Sequence[CaseAttempt],
    *,
    workspace_id: str,
    run_id: str,
    version_id: str,
    now: datetime,
) -> tuple[EvalUsageRow, ...]:
    rows: list[EvalUsageRow] = []
    for attempt in attempts:
        if not attempt.dispatched:
            continue
        if attempt.provider_config_id is None or attempt.upstream_model is None:
            continue
        rows.append(
            EvalUsageRow(
                call_id=f"{CALL_ID_PREFIX}{ULID()}",
                workspace_id=workspace_id,
                run_id=run_id,
                case_id=attempt.case_id,
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
        )
    return tuple(rows)


async def _refuse(
    sessionmaker: async_sessionmaker[AsyncSession],
    claimed: ClaimedRun,
    reason: RefusalReason,
    now: datetime,
) -> RunStatus:
    async with workspace_transaction(sessionmaker, claimed.workspace_id) as db:
        await commands.mark_refused(db, run_id=claimed.run_id, reason=reason, now=now)

    run_total.labels(status=RunStatus.REFUSED.value).inc()
    log.info(
        "evaluation.run_refused",
        workspace_id=claimed.workspace_id,
        prompt_id=claimed.prompt_id,
        run_id=claimed.run_id,
        reason=reason.value,
    )
    return RunStatus.REFUSED


async def _interrupt(
    sessionmaker: async_sessionmaker[AsyncSession],
    claimed: ClaimedRun,
    now: datetime,
) -> RunStatus:
    async with workspace_transaction(sessionmaker, claimed.workspace_id) as db:
        await commands.mark_interrupted(db, run_id=claimed.run_id, now=now)
        await events.eval_run_interrupted(
            db,
            workspace_id=claimed.workspace_id,
            actor_id=None,
            prompt_id=claimed.prompt_id,
            run_id=claimed.run_id,
            occurred_at=now,
        )

    run_total.labels(status=RunStatus.INTERRUPTED.value).inc()
    return RunStatus.INTERRUPTED


async def execute_run(
    sessionmaker: async_sessionmaker[AsyncSession],
    claimed: ClaimedRun,
    *,
    clock: Callable[[], datetime] = _utc_now,
    dispatcher: Dispatcher = dispatch,
    ceiling_check: Callable[..., Awaitable[Any]] = check_spend_ceiling,
    pricer: Callable[..., Awaitable[None]] = price_usage,
    totaller: Callable[..., Awaitable[Any]] = get_run_totals,
    concurrency: int = PER_RUN_CONCURRENCY,
) -> RunStatus:
    started = time.perf_counter()

    async with workspace_transaction(sessionmaker, claimed.workspace_id) as db:
        run = await repository.load_run(db, claimed.run_id)
        suite = await repository.load_suite(db, claimed.suite_id)
        cases = await repository.list_cases(db, claimed.suite_id)
        revision = await get_revision(db, claimed.version_id)

    if run is None or suite is None or revision is None:
        log.warning(
            "evaluation.run_unresolvable",
            workspace_id=claimed.workspace_id,
            prompt_id=claimed.prompt_id,
            run_id=claimed.run_id,
            version_id=claimed.version_id,
        )
        return await _interrupt(sessionmaker, claimed, clock())

    decision = await ceiling_check(sessionmaker, claimed.workspace_id, now=clock())
    if not decision.allowed:
        return await _refuse(
            sessionmaker, claimed, RefusalReason.SPEND_CEILING_REACHED, clock()
        )

    bindable = revision.provider_config_id is not None and revision.upstream_model is not None

    attempts: list[CaseAttempt] = []
    if cases and bindable:
        probe = await _run_case(
            sessionmaker,
            cases[0],
            revision,
            workspace_id=claimed.workspace_id,
            modality=suite.output_modality,
            dispatcher=dispatcher,
        )

        if probe.outcome is not CaseOutcome.ERROR:
            try:
                check_modality(suite.output_modality, probe.output_content)
            except ModalityMismatch as mismatch:
                modality_mismatch_total.inc()
                log.warning(
                    "evaluation.modality_mismatch",
                    workspace_id=claimed.workspace_id,
                    prompt_id=claimed.prompt_id,
                    run_id=claimed.run_id,
                    suite_id=claimed.suite_id,
                    outcome=mismatch.returned,
                )
                return await _refuse(
                    sessionmaker, claimed, RefusalReason.MODALITY_MISMATCH, clock()
                )

        attempts.append(probe)

        gate = asyncio.Semaphore(concurrency)

        async def bounded(case: CaseRow) -> CaseAttempt:
            async with gate:
                return await _run_case(
                    sessionmaker,
                    case,
                    revision,
                    workspace_id=claimed.workspace_id,
                    modality=suite.output_modality,
                    dispatcher=dispatcher,
                )

        attempts.extend(await asyncio.gather(*(bounded(case) for case in cases[1:])))
    elif cases:
        attempts.extend(_unbindable(case, revision) for case in cases)

    now = clock()
    pass_count = sum(1 for a in attempts if a.outcome is CaseOutcome.PASS)
    fail_count = sum(1 for a in attempts if a.outcome is CaseOutcome.FAIL)
    error_count = sum(1 for a in attempts if a.outcome is CaseOutcome.ERROR)

    measured = [a for a in attempts if a.input_tokens is not None and a.output_tokens is not None]
    input_tokens = sum(a.input_tokens or 0 for a in measured) if measured else None
    output_tokens = sum(a.output_tokens or 0 for a in measured) if measured else None

    async with workspace_transaction(sessionmaker, claimed.workspace_id) as db:
        for attempt in attempts:
            await commands.record_case_result(
                db,
                workspace_id=claimed.workspace_id,
                run_id=claimed.run_id,
                case_id=attempt.case_id,
                outcome=attempt.outcome,
                assertion_results=attempt.assertion_results,
                output_content=attempt.output_content,
                latency_ms=attempt.latency_ms,
                input_tokens=attempt.input_tokens,
                output_tokens=attempt.output_tokens,
                error_code=attempt.error_code,
                attempt_count=attempt.attempt_count,
                now=now,
            )

        await commands.mark_completed(
            db,
            run_id=claimed.run_id,
            pass_count=pass_count,
            fail_count=fail_count,
            error_count=error_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_amount=None,
            cost_currency=None,
            priced_at=None,
            now=now,
        )

        await events.eval_run_completed(
            db,
            workspace_id=claimed.workspace_id,
            actor_id=None,
            prompt_id=claimed.prompt_id,
            run_id=claimed.run_id,
            occurred_at=now,
        )

    await _price(
        sessionmaker,
        claimed,
        attempts,
        pricer=pricer,
        totaller=totaller,
        now=now,
    )

    run_duration_seconds.labels(
        role=run.role.value, status=RunStatus.COMPLETED.value
    ).observe(time.perf_counter() - started)
    run_total.labels(status=RunStatus.COMPLETED.value).inc()

    log.info(
        "evaluation.run_completed",
        workspace_id=claimed.workspace_id,
        prompt_id=claimed.prompt_id,
        version_id=claimed.version_id,
        suite_id=claimed.suite_id,
        run_id=claimed.run_id,
        status=RunStatus.COMPLETED.value,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return RunStatus.COMPLETED


async def run_claimed_batch(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    max_concurrent_runs: int = MAX_CONCURRENT_RUNS,
    **execution: Any,
) -> int:
    claimed: list[ClaimedRun] = []
    for _ in range(max_concurrent_runs):
        found = await claim_next_run(sessionmaker, max_concurrent_runs=max_concurrent_runs)
        if found is None:
            break
        claimed.append(found)

    if not claimed:
        return 0

    await asyncio.gather(
        *(execute_run(sessionmaker, run, **execution) for run in claimed)
    )
    return len(claimed)


async def _price(
    sessionmaker: async_sessionmaker[AsyncSession],
    claimed: ClaimedRun,
    attempts: Sequence[CaseAttempt],
    *,
    pricer: Callable[..., Awaitable[None]],
    totaller: Callable[..., Awaitable[Any]],
    now: datetime,
) -> None:
    rows = _usage_rows(
        attempts,
        workspace_id=claimed.workspace_id,
        run_id=claimed.run_id,
        version_id=claimed.version_id,
        now=now,
    )
    if not rows:
        return

    try:
        await pricer(sessionmaker, claimed.run_id, rows)
        totals = await totaller(sessionmaker, claimed.workspace_id, claimed.run_id)
    except Exception as error:
        unpriced_run_total.labels(reason="ledger_unavailable").inc()
        log.warning(
            "evaluation.pricing_unavailable",
            workspace_id=claimed.workspace_id,
            run_id=claimed.run_id,
            reason=type(error).__name__,
        )
        return

    if totals.unknown_usage_count:
        unpriced_run_total.labels(reason="unknown_usage").inc()
        return

    if totals.cost is None or totals.unpriced_count:
        unpriced_run_total.labels(reason="no_price_row").inc()
        return

    async with workspace_transaction(sessionmaker, claimed.workspace_id) as db:
        await commands.stamp_price(
            db,
            run_id=claimed.run_id,
            cost_amount=totals.cost,
            cost_currency=totals.currency,
            priced_at=now,
        )

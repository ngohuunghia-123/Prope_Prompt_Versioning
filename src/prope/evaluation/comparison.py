from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation

from prope.evaluation.domain import (
    COST_WARNING_THRESHOLD,
    CaseComparison,
    CaseResultRow,
    CaseRow,
    CostDelta,
    RunRow,
    RunStatus,
    SuiteSummary,
    SuiteVersionMismatch,
    WithheldReason,
)

__all__ = [
    "RunMeasurement",
    "compare_cases",
    "cost_delta",
    "is_cost_warning",
    "measure",
    "requires_acknowledgement",
    "roll_up",
]


@dataclass(frozen=True, slots=True)
class RunMeasurement:
    run_id: str
    suite_id: str
    status: RunStatus
    error_count: int
    input_tokens: int | None
    output_tokens: int | None
    cost: Decimal | None
    currency: str | None
    priced: bool


def measure(run: RunRow) -> RunMeasurement:
    return RunMeasurement(
        run_id=run.id,
        suite_id=run.suite_id,
        status=run.status,
        error_count=run.error_count,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost=run.cost_amount,
        currency=run.cost_currency,
        priced=run.priced_at is not None,
    )


def cost_delta(
    candidate: RunMeasurement, baseline: RunMeasurement | None
) -> tuple[CostDelta | None, WithheldReason | None]:
    if baseline is None:
        return None, WithheldReason.NO_BASELINE

    if candidate.suite_id != baseline.suite_id:
        raise SuiteVersionMismatch(candidate.suite_id, baseline.suite_id)

    if candidate.status is not RunStatus.COMPLETED or baseline.status is not RunStatus.COMPLETED:
        return None, WithheldReason.RUN_INCOMPLETE

    if candidate.error_count or baseline.error_count:
        return None, WithheldReason.HAS_ERRORS

    if candidate.input_tokens is None or baseline.input_tokens is None:
        return None, WithheldReason.UNKNOWN_USAGE

    if candidate.output_tokens is None or baseline.output_tokens is None:
        return None, WithheldReason.UNKNOWN_USAGE

    if not candidate.priced or not baseline.priced:
        return None, WithheldReason.UNPRICED

    if candidate.cost is None or baseline.cost is None:
        return None, WithheldReason.UNPRICED

    if candidate.currency != baseline.currency:
        return None, WithheldReason.MIXED_CURRENCY

    try:
        ratio = candidate.cost / baseline.cost
    except (DivisionByZero, InvalidOperation):
        ratio = None

    return (
        CostDelta(
            input_tokens=candidate.input_tokens - baseline.input_tokens,
            output_tokens=candidate.output_tokens - baseline.output_tokens,
            cost=candidate.cost - baseline.cost,
            currency=candidate.currency,
            ratio=ratio,
        ),
        None,
    )


def is_cost_warning(delta: CostDelta | None) -> bool:
    if delta is None or delta.ratio is None:
        return False
    return delta.ratio >= Decimal(1) + COST_WARNING_THRESHOLD


def compare_cases(
    cases: Sequence[CaseRow],
    candidate_results: Sequence[CaseResultRow],
    baseline_results: Sequence[CaseResultRow],
) -> tuple[CaseComparison, ...]:
    candidate_by_case = {result.case_id: result for result in candidate_results}
    baseline_by_case = {result.case_id: result for result in baseline_results}

    comparisons: list[CaseComparison] = []
    for case in cases:
        candidate = candidate_by_case.get(case.id)
        if candidate is None:
            continue
        baseline = baseline_by_case.get(case.id)
        baseline_outcome = None if baseline is None else baseline.outcome
        comparisons.append(
            CaseComparison(
                case_id=case.id,
                name=case.name,
                baseline_outcome=baseline_outcome,
                candidate_outcome=candidate.outcome,
                changed=baseline_outcome is not None and baseline_outcome != candidate.outcome,
            )
        )
    return tuple(comparisons)


def roll_up(
    summaries: Sequence[SuiteSummary],
) -> tuple[CostDelta | None, WithheldReason | None, bool]:
    if not summaries:
        return None, WithheldReason.NO_BASELINE, False

    withheld = next(
        (summary.withheld_reason for summary in summaries if summary.withheld_reason is not None),
        None,
    )
    warning = any(summary.cost_warning for summary in summaries)

    if withheld is not None:
        return None, withheld, warning

    deltas = [summary.cost_delta for summary in summaries if summary.cost_delta is not None]
    if not deltas:
        return None, WithheldReason.NO_BASELINE, warning

    currencies = {delta.currency for delta in deltas}
    if len(currencies) > 1:
        return None, WithheldReason.MIXED_CURRENCY, warning

    total_cost = sum((delta.cost for delta in deltas if delta.cost is not None), Decimal(0))

    return (
        CostDelta(
            input_tokens=sum(delta.input_tokens for delta in deltas),
            output_tokens=sum(delta.output_tokens for delta in deltas),
            cost=total_cost,
            currency=next(iter(currencies)),
            ratio=None,
        ),
        None,
        warning,
    )


def requires_acknowledgement(summaries: Sequence[SuiteSummary]) -> bool:
    return any(summary.fail_count > 0 for summary in summaries)

from sqlalchemy.ext.asyncio import AsyncSession

from prope.evaluation import comparison, repository
from prope.evaluation.domain import (
    ComparisonBlock,
    ReviewSummary,
    RunRow,
    SuiteSummary,
)
from prope.prompt_registry.seams import get_released_revision

__all__ = ["get_comparison", "get_review_summary", "latest_run_per_suite"]


def latest_run_per_suite(runs: tuple[RunRow, ...]) -> tuple[RunRow, ...]:
    newest: dict[str, RunRow] = {}
    for run in runs:
        current = newest.get(run.suite_id)
        if current is None or run.id > current.id:
            newest[run.suite_id] = run
    return tuple(newest[suite_id] for suite_id in sorted(newest))


async def _released_version_id(db: AsyncSession, prompt_id: str) -> str | None:
    released = await get_released_revision(db, prompt_id)
    return None if released is None else released.version_id


async def get_review_summary(
    db: AsyncSession, prompt_id: str, version_id: str
) -> ReviewSummary:
    released_version_id = await _released_version_id(db, prompt_id)
    runs = latest_run_per_suite(
        await repository.list_runs_for_version(db, prompt_id, version_id)
    )

    summaries: list[SuiteSummary] = []
    for run in runs:
        suite = await repository.load_suite(db, run.suite_id)
        if suite is None:
            continue

        baseline = None
        if released_version_id is not None and released_version_id != version_id:
            baseline = await repository.find_baseline_run(db, released_version_id, run.suite_id)

        delta, withheld = comparison.cost_delta(
            comparison.measure(run),
            None if baseline is None else comparison.measure(baseline),
        )

        summaries.append(
            SuiteSummary(
                suite_id=suite.id,
                suite_name=suite.name,
                suite_version=suite.suite_version,
                run_id=run.id,
                status=run.status,
                pass_count=run.pass_count,
                fail_count=run.fail_count,
                error_count=run.error_count,
                case_count=suite.case_count,
                baseline_run_id=None if baseline is None else baseline.id,
                baseline_ran_at=None if baseline is None else baseline.finished_at,
                baseline_reused=baseline is not None,
                cost_delta=delta,
                withheld_reason=withheld,
                cost_warning=comparison.is_cost_warning(delta),
            )
        )

    total_delta, total_withheld, warning = comparison.roll_up(summaries)

    return ReviewSummary(
        prompt_id=prompt_id,
        version_id=version_id,
        suites=tuple(summaries),
        total_cost_delta=total_delta,
        withheld_reason=total_withheld,
        cost_warning=warning,
        requires_acknowledgement=comparison.requires_acknowledgement(summaries),
    )


async def get_comparison(
    db: AsyncSession, prompt_id: str, candidate_version_id: str
) -> tuple[ComparisonBlock, ...]:
    released_version_id = await _released_version_id(db, prompt_id)
    runs = latest_run_per_suite(
        await repository.list_runs_for_version(db, prompt_id, candidate_version_id)
    )

    blocks: list[ComparisonBlock] = []
    for run in runs:
        suite = await repository.load_suite(db, run.suite_id)
        if suite is None:
            continue

        baseline = None
        if released_version_id is not None and released_version_id != candidate_version_id:
            baseline = await repository.find_baseline_run(db, released_version_id, run.suite_id)

        cases = await repository.list_cases(db, run.suite_id)
        candidate_results = await repository.list_case_results(db, run.id)
        baseline_results = (
            () if baseline is None else await repository.list_case_results(db, baseline.id)
        )

        delta, withheld = comparison.cost_delta(
            comparison.measure(run),
            None if baseline is None else comparison.measure(baseline),
        )

        blocks.append(
            ComparisonBlock(
                suite_id=suite.id,
                suite_name=suite.name,
                suite_version=suite.suite_version,
                candidate_run_id=run.id,
                baseline_run_id=None if baseline is None else baseline.id,
                baseline_ran_at=None if baseline is None else baseline.finished_at,
                cases=comparison.compare_cases(cases, candidate_results, baseline_results),
                cost_delta=delta,
                withheld_reason=withheld,
                cost_warning=comparison.is_cost_warning(delta),
            )
        )

    return tuple(blocks)

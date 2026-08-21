import {
  caseTotal,
  type EvalRunSummary,
  type UsageCost,
} from '@/features/prompt-lifecycle/insightsTypes';

export type EvaluationEvidenceState = 'empty' | 'running' | 'stale' | 'attention' | 'ready';

export interface EvaluationEvidenceSummary {
  state: EvaluationEvidenceState;
  latestRuns: EvalRunSummary[];
  passed: number;
  failed: number;
  errored: number;
  cases: number;
  costs: UsageCost[];
  lastFinishedAt: string | null;
}

/** Runs arrive newest first, so the first run for a suite is its current evidence. */
export function latestEvaluationRuns(runs: EvalRunSummary[]): EvalRunSummary[] {
  const latest = new Map<string, EvalRunSummary>();
  for (const run of runs) {
    if (!latest.has(run.suite_id)) latest.set(run.suite_id, run);
  }
  return [...latest.values()];
}

export function summarizeEvaluationEvidence(
  runs: EvalRunSummary[],
  hasStaleAttachment: boolean,
): EvaluationEvidenceSummary {
  const latestRuns = latestEvaluationRuns(runs);
  const passed = latestRuns.reduce((total, run) => total + run.pass_count, 0);
  const failed = latestRuns.reduce((total, run) => total + run.fail_count, 0);
  const errored = latestRuns.reduce((total, run) => total + run.error_count, 0);
  const cases = latestRuns.reduce((total, run) => total + caseTotal(run), 0);
  const running = latestRuns.some((run) => run.status === 'queued' || run.status === 'running');
  const incomplete = latestRuns.some(
    (run) => run.status === 'interrupted' || run.status === 'refused',
  );

  const costByCurrency = new Map<string, number>();
  for (const run of latestRuns) {
    if (run.cost_amount !== null && run.cost_currency !== null) {
      costByCurrency.set(
        run.cost_currency,
        (costByCurrency.get(run.cost_currency) ?? 0) + run.cost_amount,
      );
    }
  }

  const finishedTimes = latestRuns
    .map((run) => run.finished_at)
    .filter((value): value is string => value !== null)
    .sort((left, right) => right.localeCompare(left));

  const state: EvaluationEvidenceState =
    latestRuns.length === 0
      ? 'empty'
      : running
        ? 'running'
        : hasStaleAttachment
          ? 'stale'
          : incomplete || failed + errored > 0
            ? 'attention'
            : 'ready';

  return {
    state,
    latestRuns,
    passed,
    failed,
    errored,
    cases,
    costs: [...costByCurrency].map(([currency, amount]) => ({ currency, amount })),
    lastFinishedAt: finishedTimes[0] ?? null,
  };
}

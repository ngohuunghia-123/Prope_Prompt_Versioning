import type { EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';

/** Runs arrive newest first, so the first run for a suite is its current evidence. */
export function latestEvaluationRuns(runs: EvalRunSummary[]): EvalRunSummary[] {
  const latest = new Map<string, EvalRunSummary>();
  for (const run of runs) {
    if (!latest.has(run.suite_id)) latest.set(run.suite_id, run);
  }
  return [...latest.values()];
}

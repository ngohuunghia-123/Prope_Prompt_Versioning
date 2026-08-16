import { useTranslation } from 'react-i18next';

import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { caseTotal, type EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface EvaluationKpiGridProps {
  /** This revision's runs, newest first. */
  runs: EvalRunSummary[];
}

/**
 * How this revision did, across every suite it was run against.
 *
 * **There is no average score, and there was never anything to compute one
 * from.** The mock showed a figure out of ten; evaluation records a per-case
 * `outcome` and a list of assertion results, and no number in the schema is a
 * score. Pass rate is the real measure and it is the first tile.
 *
 * The rate is computed over the **latest run of each suite**, not over every run
 * ever: re-running the same suite after a fix would otherwise leave the old
 * failures dragging the number down forever.
 */
export function EvaluationKpiGrid({ runs }: EvaluationKpiGridProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  // Runs arrive newest first, so the first sighting of a suite is its latest run.
  const latestPerSuite = new Map<string, EvalRunSummary>();
  for (const run of runs) {
    if (!latestPerSuite.has(run.suite_id)) latestPerSuite.set(run.suite_id, run);
  }
  const current = [...latestPerSuite.values()];

  const passed = current.reduce((total, run) => total + run.pass_count, 0);
  const failed = current.reduce((total, run) => total + run.fail_count, 0);
  const errored = current.reduce((total, run) => total + run.error_count, 0);
  const cases = current.reduce((total, run) => total + caseTotal(run), 0);

  const cost = new Map<string, number>();
  for (const run of current) {
    if (run.cost_amount !== null && run.cost_currency !== null) {
      cost.set(run.cost_currency, (cost.get(run.cost_currency) ?? 0) + run.cost_amount);
    }
  }
  const priced = format.costs([...cost].map(([currency, amount]) => ({ currency, amount })));

  const metrics = [
    {
      label: t('lifecycle.insights.evaluation.passRate'),
      // No cases means no rate — not 0%, which reads as "everything failed".
      value: cases === 0 ? '—' : format.percent(passed / cases),
      detail: t('lifecycle.insights.evaluation.acrossSuites', { count: current.length }),
    },
    {
      label: t('lifecycle.insights.evaluation.cases'),
      value: `${format.number(passed)} / ${format.number(cases)}`,
      detail: failed + errored > 0
        ? t('lifecycle.insights.evaluation.failedAndErrored', { failed, errored })
        : undefined,
    },
    {
      label: t('lifecycle.insights.evaluation.cost'),
      value: priced ?? t('lifecycle.insights.unpriced'),
      detail: t('lifecycle.insights.evaluation.costDetail'),
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {metrics.map((metric) => (
        <MetricTile key={metric.label} label={metric.label} value={metric.value} detail={metric.detail} />
      ))}
    </div>
  );
}

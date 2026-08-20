import { Database } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';

import { StatusBadge } from '@/components/StatusBadge';
import { caseTotal, passRate, type EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface EvaluationSuiteTableProps {
  /** The latest run of each suite, for the selected revision. */
  runs: EvalRunSummary[];
  onSelect: (run: EvalRunSummary) => void;
}

/** Green only for a clean sweep. Anything that failed is not a pass. */
function toneFor(run: EvalRunSummary): 'active' | 'pending' | 'error' {
  if (run.status !== 'completed') return 'pending';
  return run.fail_count + run.error_count === 0 ? 'active' : 'error';
}

/**
 * One row per suite: what it is, how it went, and what it cost.
 *
 * **Named by its dataset where there is one.** A suite materialised from an
 * attached dataset carries `dataset_name`, which is the name the person chose in
 * the library and therefore the one they will recognise. A hand-authored suite
 * has no dataset behind it, so it shows its own name and no second line — an
 * absence, not an empty cell.
 */
export function EvaluationSuiteTable({ runs, onSelect }: EvaluationSuiteTableProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  const title = (run: EvalRunSummary) =>
    run.dataset_name ?? run.suite_name ?? t('lifecycle.insights.evaluation.unnamedSuite');

  const rate = (run: EvalRunSummary) => {
    const value = passRate(run);
    return value === null ? '—' : format.percent(value);
  };

  return (
    <section aria-labelledby="evaluation-suites-title" className="overflow-hidden bg-surface">
      <h2 id="evaluation-suites-title" className="sr-only">{t('lifecycle.insights.evaluation.suites')}</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-3xl border-collapse text-left">
          <thead className="border-b border-border bg-subtle text-overline font-bold tracking-navigation-overline text-muted uppercase">
            <tr>
              <th scope="col" className="px-5 py-4">{t('lifecycle.insights.evaluation.suite')}</th>
              <th scope="col" className="px-4 py-4 text-right">{t('lifecycle.insights.evaluation.passRate')}</th>
              <th scope="col" className="px-4 py-4 text-right">{t('lifecycle.insights.evaluation.cases')}</th>
              <th scope="col" className="px-4 py-4 text-right">{t('lifecycle.insights.evaluation.cost')}</th>
              <th scope="col" className="px-4 py-4">{t('lifecycle.insights.evaluation.lastRun')}</th>
              <th scope="col" className="px-5 py-4">{t('lifecycle.insights.evaluation.status')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {runs.map((run) => (
              <tr key={run.run_id} tabIndex={0} role="button" onClick={() => onSelect(run)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(run); } }} className="cursor-pointer transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/70 focus-visible:outline-2 focus-visible:outline-focus">
                <th scope="row" className="px-5 py-4 font-semibold text-ink">
                  <span className="flex items-center gap-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-secondary">
                      <Database aria-hidden className="size-5" weight="duotone" />
                    </span>
                    <span>
                      {title(run)}
                      {run.suite_name && run.dataset_name ? (
                        <span className="mt-0.5 block text-caption font-normal text-muted">
                          {t('lifecycle.insights.evaluation.suiteVersion', {
                            name: run.suite_name,
                            version: run.suite_version ?? 1,
                          })}
                        </span>
                      ) : null}
                    </span>
                  </span>
                </th>
                <td className="px-4 py-4 text-right text-body font-semibold text-ink">{rate(run)}</td>
                <td className="px-4 py-4 text-right text-body text-muted">
                  {format.number(run.pass_count)} / {format.number(caseTotal(run))}
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-right text-body text-muted">
                  {run.cost_amount === null || run.cost_currency === null
                    ? t('lifecycle.insights.unpriced')
                    : format.money(run.cost_amount, run.cost_currency)}
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-body text-muted">
                  {run.finished_at ? format.dateTime(run.finished_at) : '—'}
                </td>
                <td className="px-5 py-4">
                  <StatusBadge tone={toneFor(run)}>{t(`lifecycle.insights.runStatus.${run.status}`)}</StatusBadge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

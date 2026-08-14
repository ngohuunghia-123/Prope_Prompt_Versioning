import { Database } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { EvaluationDatasetSummary } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface EvaluationDatasetTableProps {
  datasets: EvaluationDatasetSummary[];
}

export function EvaluationDatasetTable({ datasets }: EvaluationDatasetTableProps) {
  const { t, i18n } = useTranslation();
  const format = useLocaleFormatters();
  const decimal = new Intl.NumberFormat(i18n.resolvedLanguage ?? i18n.language, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  return (
    <section aria-labelledby="evaluation-datasets-title" className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
      <h2 id="evaluation-datasets-title" className="sr-only">{t('lifecycle.overview.evaluation.datasets')}</h2>
      <div className="grid gap-3 p-3 sm:hidden">
        {datasets.map((dataset) => (
          <article key={dataset.id} className="rounded-xl border border-border bg-canvas p-4">
            <div className="flex items-center gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-secondary">
                <Database aria-hidden className="size-5" weight="duotone" />
              </span>
              <h3 className="text-body font-semibold text-ink">{dataset.name}</h3>
            </div>
            <dl className="mt-4 grid grid-cols-3 gap-3 text-caption">
              <div><dt className="text-muted">{t('lifecycle.overview.evaluation.passRate')}</dt><dd className="mt-1 font-semibold text-ink">{format.percent(dataset.passRate)}</dd></div>
              <div><dt className="text-muted">{t('lifecycle.overview.evaluation.averageScore')}</dt><dd className="mt-1 font-semibold text-ink">{decimal.format(dataset.averageScore)}</dd></div>
              <div><dt className="text-muted">{t('lifecycle.overview.evaluation.evalRuns')}</dt><dd className="mt-1 font-semibold text-ink">{format.number(dataset.evalRuns)}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full border-collapse text-left">
          <thead className="border-b border-border bg-subtle text-overline font-bold tracking-navigation-overline text-muted uppercase">
            <tr>
              <th scope="col" className="px-5 py-4">{t('lifecycle.overview.evaluation.dataset')}</th>
              <th scope="col" className="px-5 py-4 text-right">{t('lifecycle.overview.evaluation.passRate')}</th>
              <th scope="col" className="px-5 py-4 text-right">{t('lifecycle.overview.evaluation.averageScore')}</th>
              <th scope="col" className="px-5 py-4 text-right">{t('lifecycle.overview.evaluation.evalRuns')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {datasets.map((dataset) => (
              <tr key={dataset.id} className="transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/70">
                <th scope="row" className="px-5 py-5 font-semibold text-ink">
                  <span className="flex items-center gap-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-secondary"><Database aria-hidden className="size-5" weight="duotone" /></span>
                    {dataset.name}
                  </span>
                </th>
                <td className="px-5 py-5 text-right text-body font-semibold text-ink">{format.percent(dataset.passRate)}</td>
                <td className="px-5 py-5 text-right text-body text-ink">{decimal.format(dataset.averageScore)}</td>
                <td className="px-5 py-5 text-right text-body text-ink">{format.number(dataset.evalRuns)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

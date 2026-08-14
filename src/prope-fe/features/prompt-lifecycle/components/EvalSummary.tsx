import { CheckCircle, XCircle } from '@phosphor-icons/react';
import type { CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type { EvalDatasetResult } from '@/features/prompt-lifecycle/types';

interface EvalSummaryProps {
  datasets: EvalDatasetResult[];
  selectedDataset: EvalDatasetResult;
}

export function EvalSummary({ datasets, selectedDataset }: EvalSummaryProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const tests = datasets.flatMap((dataset) => dataset.tests);
  const passed = tests.filter((test) => test.passed).length;
  const metrics = Object.entries(selectedDataset.metrics) as [keyof EvalDatasetResult['metrics'], number][];
  return (
    <section className="grid overflow-hidden rounded-modal border border-border bg-surface shadow-panel md:grid-cols-[minmax(12rem,0.65fr)_minmax(0,1.35fr)]">
      <div className="grid place-items-center border-b border-border p-5 text-center md:border-r md:border-b-0">
        <div>
          <p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.evalWorkspace.overall')}</p>
          <p className="mt-2 font-display text-heading-1 text-ink">{t('lifecycle.evalWorkspace.passCount', { passed, total: tests.length })}</p>
          <div className="mt-3 flex items-center justify-center gap-3 text-caption">
            <span className="inline-flex items-center gap-1 text-success-text"><CheckCircle aria-hidden className="size-4" weight="fill" />{t('lifecycle.evalWorkspace.passed', { count: passed })}</span>
            <span className="inline-flex items-center gap-1 text-danger-text"><XCircle aria-hidden className="size-4" weight="fill" />{t('lifecycle.evalWorkspace.failed', { count: tests.length - passed })}</span>
          </div>
        </div>
      </div>
      <div className="p-5">
        <p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.evalWorkspace.latestDatasetRates')}</p>
        <p className="mt-1 truncate text-body font-semibold text-ink">{selectedDataset.name}</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {metrics.map(([key, value]) => (
            <div key={key} className="grid gap-2">
              <div className="flex items-center justify-between gap-3 text-caption">
                <span className="font-medium text-muted">{t(`lifecycle.evalWorkspace.metrics.${key}`)}</span>
                <span className="font-semibold text-ink">{format.percent(value)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-subtle" role="progressbar" aria-label={t(`lifecycle.evalWorkspace.metrics.${key}`)} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)}>
                <div className="h-full rounded-full bg-secondary transition-[width] duration-(--prope-motion-duration-base) ease-(--prope-motion-ease-standard)" style={{ width: `${value * 100}%` } as CSSProperties} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

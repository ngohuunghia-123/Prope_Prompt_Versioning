import { useTranslation } from 'react-i18next';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type { ProductionOverview } from '@/features/prompt-lifecycle/types';

interface ProductionMetricsProps {
  overview: ProductionOverview;
}

export function ProductionMetrics({ overview }: ProductionMetricsProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const metrics = [
    { label: t('lifecycle.overview.production.rate'), value: format.percent(overview.rate) },
    { label: t('lifecycle.overview.production.csat'), value: format.percent(overview.csat) },
    { label: t('lifecycle.overview.production.requests'), value: format.number(overview.requests) },
  ];

  return (
    <section aria-label={t('lifecycle.overview.production.metricsLabel')} className="grid gap-4 sm:grid-cols-3">
      {metrics.map((metric) => (
        <article
          key={metric.label}
          className="rounded-modal border border-border bg-surface p-5 shadow-panel transition-colors duration-(--prope-motion-duration-fast) hover:border-border-strong"
        >
          <p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{metric.label}</p>
          <p className="mt-5 font-display text-heading-1 font-semibold text-ink">{metric.value}</p>
        </article>
      ))}
    </section>
  );
}

import { useTranslation } from 'react-i18next';

import type { PromptUsage } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface ProductionMetricsProps {
  usage: PromptUsage;
}

/**
 * The window's totals, above the per-app split.
 *
 * **No CSAT tile.** The mock had one. Prope records no satisfaction signal of
 * any kind — no rating, no thumbs, no survey — so the number could only ever
 * have been invented, and a quality figure a reviewer might act on is the worst
 * place to invent one.
 */
export function ProductionMetrics({ usage }: ProductionMetricsProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  const totals = usage.buckets.reduce(
    (accumulator, bucket) => {
      accumulator.input += bucket.input_tokens;
      accumulator.output += bucket.output_tokens;
      accumulator.errors += bucket.error_count;
      accumulator.unpriced += bucket.unpriced_count;
      for (const entry of bucket.cost) {
        accumulator.cost.set(entry.currency, (accumulator.cost.get(entry.currency) ?? 0) + entry.amount);
      }
      return accumulator;
    },
    { input: 0, output: 0, errors: 0, unpriced: 0, cost: new Map<string, number>() },
  );

  const cost = format.costs([...totals.cost].map(([currency, amount]) => ({ currency, amount })));

  const metrics = [
    { label: t('lifecycle.insights.production.requests'), value: format.number(usage.total_requests), detail: null },
    {
      label: t('lifecycle.insights.production.tokens'),
      value: `${format.number(totals.input)} / ${format.number(totals.output)}`,
      detail: t('lifecycle.insights.production.tokensDetail'),
    },
    {
      label: t('lifecycle.insights.production.cost'),
      value: cost ?? t('lifecycle.insights.unpriced'),
      detail: totals.unpriced > 0 ? t('lifecycle.insights.production.unpricedCalls', { count: totals.unpriced }) : null,
    },
    {
      label: t('lifecycle.insights.production.errorRate'),
      value: format.percent(usage.total_requests === 0 ? 0 : totals.errors / usage.total_requests),
      detail: null,
    },
  ];

  return (
    <section aria-label={t('lifecycle.insights.production.metricsLabel')} className="grid bg-surface sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <article
          key={metric.label}
          className="border-b border-border p-5 transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/50 sm:border-r"
        >
          <p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{metric.label}</p>
          <p className="mt-4 font-display text-heading-2 font-semibold break-words text-ink">{metric.value}</p>
          {metric.detail ? <p className="mt-1 text-caption text-muted">{metric.detail}</p> : null}
        </article>
      ))}
    </section>
  );
}

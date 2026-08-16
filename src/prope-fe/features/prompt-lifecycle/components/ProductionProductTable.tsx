import { useTranslation } from 'react-i18next';

import { Tag } from '@/components/Tag';
import { INTERNAL_APP_LABEL } from '@/features/workspace/keyTypes';
import { appLabel, type UsageBucket } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface ProductionProductTableProps {
  buckets: UsageBucket[];
  totalRequests: number;
}

/**
 * One row per calling integration, busiest first.
 *
 * **Share is computed here from `requests / totalRequests`**, not sent by the
 * server. Two numbers that must agree are better than three.
 *
 * The internal row is marked rather than hidden or merged. It is a person's own
 * playground turns against this prompt: real spend, and not something a reader
 * should mistake for a product calling in.
 */
export function ProductionProductTable({ buckets, totalRequests }: ProductionProductTableProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  return (
    <section
      aria-label={t('lifecycle.insights.production.byApp')}
      className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-3xl border-collapse text-left text-body">
          <caption className="sr-only">{t('lifecycle.insights.production.byApp')}</caption>
          <thead className="bg-subtle text-overline font-bold tracking-navigation-overline text-muted uppercase">
            <tr>
              <th scope="col" className="px-5 py-3 sm:px-6">{t('lifecycle.insights.production.app')}</th>
              <th scope="col" className="px-4 py-3 text-right">{t('lifecycle.insights.production.share')}</th>
              <th scope="col" className="px-4 py-3 text-right">{t('lifecycle.insights.production.requests')}</th>
              <th scope="col" className="px-4 py-3 text-right">{t('lifecycle.insights.production.tokens')}</th>
              <th scope="col" className="px-4 py-3 text-right">{t('lifecycle.insights.production.cost')}</th>
              <th scope="col" className="px-5 py-3 text-right sm:px-6">{t('lifecycle.insights.production.errorRate')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {buckets.map((bucket) => {
              const share = totalRequests === 0 ? 0 : bucket.requests / totalRequests;
              const cost = format.costs(bucket.cost);
              const internal = bucket.consumer_key_id === null;
              return (
                <tr
                  key={bucket.consumer_key_id ?? '__internal__'}
                  className="transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/60"
                >
                  <th scope="row" className="px-5 py-4 font-semibold text-ink sm:px-6">
                    <span className="flex flex-wrap items-center gap-2">
                      {appLabel(bucket, INTERNAL_APP_LABEL)}
                      {internal ? <Tag state="neutral">{t('lifecycle.insights.production.internalTag')}</Tag> : null}
                    </span>
                    {bucket.last_called_at ? (
                      <span className="mt-1 block text-caption font-normal text-muted">
                        {t('lifecycle.insights.production.lastCalled', { when: format.dateTime(bucket.last_called_at) })}
                      </span>
                    ) : null}
                  </th>
                  <td className="px-4 py-4 text-right align-top">
                    <span className="block font-medium text-ink">{format.percent(share)}</span>
                    <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden>
                      <span
                        className="block h-full rounded-full bg-secondary"
                        style={{ width: `${Math.round(share * 100)}%` }}
                      />
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right align-top font-medium text-ink">{format.number(bucket.requests)}</td>
                  <td className="whitespace-nowrap px-4 py-4 text-right align-top text-muted">
                    {format.number(bucket.input_tokens)} / {format.number(bucket.output_tokens)}
                  </td>
                  <td className="px-4 py-4 text-right align-top">
                    {/* An empty cost list is not zero — it means nothing in this
                        bucket could be priced, and the count below says how much. */}
                    <span className="block font-medium text-ink">{cost ?? t('lifecycle.insights.unpriced')}</span>
                    {bucket.unpriced_count > 0 ? (
                      <span className="mt-1 block text-caption text-warning-strong">
                        {t('lifecycle.insights.production.unpricedCalls', { count: bucket.unpriced_count })}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-5 py-4 text-right align-top sm:px-6">
                    <span className="font-medium text-ink">
                      {format.percent(bucket.requests === 0 ? 0 : bucket.error_count / bucket.requests)}
                    </span>
                    {bucket.fallback_count > 0 ? (
                      <span className="mt-1 block text-caption text-muted">
                        {t('lifecycle.insights.production.fallbacks', { count: bucket.fallback_count })}
                      </span>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

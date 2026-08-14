import { useTranslation } from 'react-i18next';
import type { ProductionOverviewProduct } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface ProductionProductTableProps {
  products: ProductionOverviewProduct[];
}

const badgeTone: Record<string, string> = {
  shopee: 'bg-warning text-warning-strong',
  lazada: 'bg-info text-info-strong',
  tiktok: 'bg-subtle text-ink',
  other: 'bg-success text-success-text',
};

export function ProductionProductTable({ products }: ProductionProductTableProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();

  return (
    <section aria-label={t('lifecycle.overview.production.productPerformance')} className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
      <div className="overflow-x-auto">
        <table className="w-full min-w-152 border-collapse text-left text-body">
          <caption className="sr-only">{t('lifecycle.overview.production.productPerformance')}</caption>
          <thead className="bg-subtle text-overline font-bold tracking-navigation-overline text-muted uppercase">
            <tr>
              <th scope="col" className="px-5 py-3 sm:px-6">{t('lifecycle.overview.production.product')}</th>
              <th scope="col" className="px-4 py-3 text-right">{t('lifecycle.overview.production.rate')}</th>
              <th scope="col" className="px-4 py-3 text-right">{t('lifecycle.overview.production.csat')}</th>
              <th scope="col" className="px-5 py-3 text-right sm:px-6">{t('lifecycle.overview.production.requests')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {products.map((product) => (
              <tr key={product.id} className="transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/60">
                <th scope="row" className="px-5 py-5 font-semibold text-ink sm:px-6">
                  <span className="flex items-center gap-3">
                    <span className={cn('grid size-9 shrink-0 place-items-center rounded-control text-caption font-bold', badgeTone[product.id] ?? badgeTone.other)} aria-hidden>
                      {product.shortLabel}
                    </span>
                    {product.name}
                  </span>
                </th>
                <td className="px-4 py-5 text-right font-medium text-ink">{format.percent(product.rate)}</td>
                <td className="px-4 py-5 text-right font-medium text-ink">{format.percent(product.csat)}</td>
                <td className="px-5 py-5 text-right font-medium text-ink sm:px-6">{format.number(product.requests)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

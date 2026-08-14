import { Link as LinkIcon } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { connectedProductsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface ConnectedProductsCardProps { promptId: string; }

export function ConnectedProductsCard({ promptId }: ConnectedProductsCardProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const productsQuery = useQuery(connectedProductsOptions(promptId));
  return (
    <Card title={t('lifecycle.overview.production.connectedProducts')} description={t('lifecycle.overview.production.connectedProductsDesc')}>
      {productsQuery.isPending ? <p role="status">{t('lifecycle.overview.production.loadingProducts')}</p> : productsQuery.isError ? <p role="alert" className="text-danger-text">{t('lifecycle.overview.production.loadError')}</p> : productsQuery.data.length ? (
        <div className="overflow-x-auto"><table className="w-full text-body"><thead><tr className="border-b border-border text-left text-caption text-muted"><th className="pb-3 pr-4">{t('lifecycle.overview.production.product')}</th><th className="pb-3 pr-4">{t('lifecycle.overview.production.type')}</th><th className="pb-3 pr-4">{t('lifecycle.overview.production.version')}</th><th className="pb-3 pr-4">{t('lifecycle.overview.production.traffic')}</th><th className="pb-3">{t('lifecycle.overview.production.lastUsed')}</th></tr></thead><tbody className="divide-y divide-border">{productsQuery.data.map((product) => (
          <tr key={product.id}><td className="py-3 pr-4"><span className="flex items-center gap-2 font-medium text-ink"><LinkIcon aria-hidden className="size-4 text-muted" />{product.name}</span></td><td className="py-3 pr-4 text-ink">{t(`lifecycle.overview.production.productTypes.${product.type}`)}</td><td className="py-3 pr-4 text-ink">{product.currentVersion}</td><td className="py-3 pr-4"><div className="flex items-center gap-2"><div className="h-2 w-20 overflow-hidden rounded-full bg-subtle"><div className="h-full rounded-full bg-primary" style={{ width: `${product.trafficPercent}%` }} /></div><span className="text-caption text-muted">{format.percent(product.trafficPercent / 100)}</span></div></td><td className="py-3 text-caption text-muted">{format.date(product.lastUsed)}</td></tr>
        ))}</tbody></table></div>
      ) : <p className="py-8 text-center text-muted">{t('lifecycle.states.empty.description')}</p>}
    </Card>
  );
}

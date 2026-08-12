import { ArrowClockwise, Code, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { callRecordsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

export function CallRecordsPage() {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const query = useQuery(callRecordsOptions);
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (query.data.length === 0) return <QueryState state="empty" />;
  const fallbackCount = query.data.filter((record) => record.outcome === 'fallback').length;
  return (
    <div className="grid gap-6">
      <PageIntro eyebrow={t('lifecycle.calls.eyebrow')} title={t('lifecycle.calls.title')} description={t('lifecycle.calls.description')} action={<Button type="button" intent="neutral" leadingIcon={<ArrowClockwise aria-hidden className="size-4" />} onClick={() => void query.refetch()}>{t('lifecycle.calls.refresh')}</Button>} />
      <div className="grid gap-4 sm:grid-cols-3"><MetricTile label={t('lifecycle.calls.total')} value={format.number(query.data.length)} /><MetricTile label={t('lifecycle.calls.fallbacks')} value={format.number(fallbackCount)} detail={t('lifecycle.calls.detectable')} /><MetricTile label={t('lifecycle.calls.versionCoverage')} value={format.percent(1)} detail={t('lifecycle.calls.durable')} /></div>
      <Card title={t('lifecycle.calls.gateway')}><div className="mt-2 flex items-start gap-3 rounded-lg border border-border bg-subtle p-4"><Code aria-hidden className="mt-0.5 size-5 shrink-0 text-secondary" /><code className="overflow-x-auto text-caption text-ink">POST /v1/chat/completions · model: commerce/checkout-assistant</code></div></Card>
      <div className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel"><div className="overflow-x-auto"><table className="w-full min-w-3xl border-collapse text-left text-body"><thead className="bg-subtle text-caption text-muted"><tr>{['prompt', 'version', 'consumer', 'time', 'usage', 'outcome'].map((column) => <th key={column} className="px-4 py-3 font-semibold">{t(`lifecycle.calls.columns.${column}`)}</th>)}</tr></thead><tbody className="divide-y divide-border">{query.data.map((record) => <tr key={record.id}><td className="px-4 py-4 font-medium text-ink">{record.promptTitle}</td><td className="px-4 py-4"><code className="text-caption text-muted">{record.versionId}</code></td><td className="px-4 py-4 text-muted">{record.consumer}</td><td className="px-4 py-4 text-muted">{format.date(record.timestamp)}</td><td className="px-4 py-4 text-muted">{format.number(record.tokens)} · {format.currency(record.cost)}</td><td className="px-4 py-4"><StatusBadge tone={record.outcome === 'success' ? 'active' : record.outcome === 'fallback' ? 'pending' : 'error'}>{t(`lifecycle.calls.outcomes.${record.outcome}`)}</StatusBadge></td></tr>)}</tbody></table></div></div>
      <p className="flex items-center gap-2 text-caption text-muted"><WarningCircle aria-hidden className="size-4" />{t('lifecycle.calls.storageNote')}</p>
    </div>
  );
}

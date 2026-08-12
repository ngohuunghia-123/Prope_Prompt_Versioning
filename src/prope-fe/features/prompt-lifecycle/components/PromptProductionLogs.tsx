import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { callRecordsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

export interface PromptProductionLogsProps { promptTitle: string; revisionId: string; }

export function PromptProductionLogs({ promptTitle, revisionId }: PromptProductionLogsProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const query = useQuery(callRecordsOptions);
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  const records = query.data.filter((record) => record.promptTitle === promptTitle && record.versionId === revisionId);
  if (!records.length) return <QueryState state="empty" />;
  return (
    <section aria-labelledby="production-log-title" className="grid gap-4">
      <div><h2 id="production-log-title" className="font-display text-heading-2 text-ink">{t('lifecycle.overview.logs.title')}</h2><p className="mt-2 text-body text-muted">{t('lifecycle.overview.logs.description')}</p></div>
      <div className="overflow-hidden rounded-xl border border-border"><div className="overflow-x-auto"><table className="w-full min-w-2xl border-collapse text-left text-body"><thead className="bg-subtle text-caption text-muted"><tr>{['time', 'consumer', 'usage', 'outcome'].map((column) => <th key={column} className="px-4 py-3 font-semibold">{t(`lifecycle.calls.columns.${column}`)}</th>)}</tr></thead><tbody className="divide-y divide-border">{records.map((record) => <tr key={record.id}><td className="px-4 py-4 text-muted">{format.date(record.timestamp)}</td><td className="px-4 py-4 font-medium text-ink">{record.consumer}</td><td className="px-4 py-4 text-muted">{format.number(record.tokens)} · {format.currency(record.cost)}</td><td className="px-4 py-4"><StatusBadge tone={record.outcome === 'success' ? 'active' : record.outcome === 'fallback' ? 'pending' : 'error'}>{t(`lifecycle.calls.outcomes.${record.outcome}`)}</StatusBadge></td></tr>)}</tbody></table></div></div>
    </section>
  );
}

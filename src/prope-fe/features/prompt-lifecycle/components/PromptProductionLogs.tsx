import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { callRecordsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

export interface PromptProductionLogsProps { promptId: string; promptTitle: string; revisionId: string; }

/**
 * What this prompt has actually served — ADR-0055's reader, on the screen it was
 * built for.
 *
 * **There is no workspace-wide version of this and there must not be.** Every call
 * record names a `prompt_id`, so a flat list would tell any member that a private
 * prompt exists, which is the disclosure BR-01 closes as not-found. The read is
 * per prompt, behind `prompt.read`, which is why this component takes a
 * `promptId` and the standalone call-records page was removed.
 *
 * **Metadata only.** Request and response bodies have no read path at all
 * (ADR-0018) — they are written and deleted, and nothing in the product can show
 * them.
 */
export function PromptProductionLogs({ promptId, promptTitle, revisionId }: PromptProductionLogsProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const query = useQuery(callRecordsOptions(promptId, promptTitle));
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  // Narrowed to the revision the reader is looking at. The API returns the
  // prompt's whole recent history, newest first, because "what has this prompt
  // served" is the question and a revision filter is a lens on it.
  const records = query.data.filter((record) => record.versionId === revisionId);
  if (!records.length) return <QueryState state="empty" />;
  return (
    <section aria-labelledby="production-log-title" className="grid gap-4">
      <div><h2 id="production-log-title" className="font-display text-heading-2 text-ink">{t('lifecycle.overview.logs.title')}</h2><p className="mt-2 text-body text-muted">{t('lifecycle.overview.logs.description')}</p></div>
      <div className="overflow-hidden rounded-xl border border-border"><div className="overflow-x-auto"><table className="w-full min-w-2xl border-collapse text-left text-body"><thead className="bg-subtle text-caption text-muted"><tr>{['time', 'consumer', 'usage', 'outcome'].map((column) => <th key={column} className="px-4 py-3 font-semibold">{t(`lifecycle.calls.columns.${column}`)}</th>)}</tr></thead><tbody className="divide-y divide-border">{records.map((record) => <tr key={record.id}><td className="px-4 py-4 text-muted">{format.date(record.timestamp)}</td><td className="px-4 py-4 font-medium text-ink">{record.consumer}</td><td className="px-4 py-4 text-muted">{format.number(record.tokens)} · {format.currency(record.cost, record.currency ?? undefined)}</td><td className="px-4 py-4"><StatusBadge tone={record.outcome === 'success' ? 'active' : record.outcome === 'fallback' ? 'pending' : 'error'}>{t(`lifecycle.calls.outcomes.${record.outcome}`)}</StatusBadge></td></tr>)}</tbody></table></div></div>
    </section>
  );
}

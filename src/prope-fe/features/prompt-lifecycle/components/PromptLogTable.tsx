import { useTranslation } from 'react-i18next';

import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import { INTERNAL_APP_LABEL } from '@/features/workspace/keyTypes';
import { appLabel, type CallOutcome, type CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';
import { cn } from '@/lib/cn';

interface PromptLogTableProps {
  records: CallRecord[];
  selectedId?: string;
  onSelect: (record: CallRecord) => void;
}

function toneFor(outcome: CallOutcome): 'active' | 'pending' | 'error' {
  if (outcome === 'ok') return 'active';
  if (outcome === 'fallback' || outcome === 'truncated') return 'pending';
  return 'error';
}

export function PromptLogTable({ records, selectedId, onSelect }: PromptLogTableProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();
  const columns = ['time', 'app', 'revision', 'model', 'tokens', 'cost', 'outcome'] as const;

  return (
    <div role="table" aria-label={t('lifecycle.insights.logs.viewerTitle')} className="min-w-0 border-t border-border text-body">
      <div role="row" className="hidden grid-cols-7 border-b border-border bg-subtle text-caption text-muted md:grid">
        {columns.map((key) => (
          <span role="columnheader" key={key} className="min-w-0 px-3 py-3 font-semibold">
            {t(`lifecycle.insights.logs.columns.${key}`)}
          </span>
        ))}
      </div>
      <div role="rowgroup" className="divide-y divide-border">
        {records.map((record) => (
          <button
            type="button"
            role="row"
            key={record.call_id}
            onClick={() => onSelect(record)}
            aria-label={t('lifecycle.insights.logs.viewLog', { id: record.call_id })}
            aria-selected={selectedId === record.call_id}
            className={cn(
              'grid w-full cursor-pointer gap-2 px-4 py-3 text-left transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus md:grid-cols-7 md:items-center md:gap-0 md:px-0',
              selectedId === record.call_id && 'bg-accent-soft',
            )}
          >
            <span role="cell" className="min-w-0 text-ink md:px-3">{format.dateTime(record.created_at)}</span>
            <span role="cell" className="min-w-0 truncate md:px-3">
              {record.consumer_key_id === null ? (
                <Tag state="neutral">{INTERNAL_APP_LABEL}</Tag>
              ) : (
                <span className="text-ink">{appLabel(record, INTERNAL_APP_LABEL)}</span>
              )}
            </span>
            <span role="cell" className="text-muted md:px-3">
              <span className="md:hidden">{t('lifecycle.insights.logs.columns.revision')}: </span>
              {record.revision_number === null ? '—' : `r${record.revision_number}`}
            </span>
            <span role="cell" className="min-w-0 break-words text-muted md:px-3">{record.upstream_model ?? '—'}</span>
            <span role="cell" className="text-muted md:px-3">
              {record.usage_status === 'unknown'
                ? t('lifecycle.insights.usageUnknown')
                : `${format.number(record.input_tokens ?? 0)} / ${format.number(record.output_tokens ?? 0)}`}
            </span>
            <span role="cell" className="text-muted md:px-3">
              {format.callCost(record.cost, record.currency, record.cost_status)}
            </span>
            <span role="cell" className="md:px-3">
              <StatusBadge tone={toneFor(record.outcome)}>{t(`lifecycle.insights.outcomes.${record.outcome}`)}</StatusBadge>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

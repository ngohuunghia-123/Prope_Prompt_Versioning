import { CaretRight } from '@phosphor-icons/react';
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

/** `ok` reads as success; a fallback or a truncation is a warning, not a failure. */
function toneFor(outcome: CallOutcome): 'active' | 'pending' | 'error' {
  if (outcome === 'ok') return 'active';
  if (outcome === 'fallback' || outcome === 'truncated') return 'pending';
  return 'error';
}

export function PromptLogTable({ records, selectedId, onSelect }: PromptLogTableProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-3xl border-collapse text-left text-body">
        <thead className="bg-subtle text-caption text-muted">
          <tr className="border-b border-border">
            {['time', 'app', 'revision', 'model', 'tokens', 'cost', 'outcome'].map((key) => (
              <th key={key} className="px-3 py-3 font-semibold">{t(`lifecycle.insights.logs.columns.${key}`)}</th>
            ))}
            <th className="w-12"><span className="sr-only">{t('lifecycle.insights.logs.viewDetail')}</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {records.map((record) => (
            <tr
              key={record.call_id}
              className={cn('transition-colors hover:bg-subtle/60', selectedId === record.call_id && 'bg-accent-soft/60')}
            >
              <td className="whitespace-nowrap px-3 py-3 text-ink">{format.dateTime(record.created_at)}</td>
              <td className="px-3 py-3">
                {/* No key means the internal caller. The id is the fallback for a
                    key whose row has gone — never a blank cell, which reads as
                    "we do not know" when we do. */}
                {record.consumer_key_id === null ? (
                  <Tag state="neutral">{INTERNAL_APP_LABEL}</Tag>
                ) : (
                  <span className="text-ink">{appLabel(record, INTERNAL_APP_LABEL)}</span>
                )}
              </td>
              <td className="whitespace-nowrap px-3 py-3 text-muted">
                {record.revision_number === null ? '—' : `r${record.revision_number}`}
              </td>
              <td className="px-3 py-3 text-muted">{record.upstream_model ?? '—'}</td>
              <td className="whitespace-nowrap px-3 py-3 text-muted">
                {record.usage_status === 'unknown'
                  ? t('lifecycle.insights.usageUnknown')
                  : `${format.number(record.input_tokens ?? 0)} / ${format.number(record.output_tokens ?? 0)}`}
              </td>
              <td className="whitespace-nowrap px-3 py-3 text-muted">
                {format.callCost(record.cost, record.currency, record.cost_status)}
              </td>
              <td className="px-3 py-3">
                <StatusBadge tone={toneFor(record.outcome)}>
                  {t(`lifecycle.insights.outcomes.${record.outcome}`)}
                </StatusBadge>
              </td>
              <td className="pr-3">
                <button
                  type="button"
                  onClick={() => onSelect(record)}
                  aria-label={t('lifecycle.insights.logs.viewLog', { id: record.call_id })}
                  className="grid size-9 place-items-center rounded-full text-muted hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
                >
                  <CaretRight aria-hidden className="size-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

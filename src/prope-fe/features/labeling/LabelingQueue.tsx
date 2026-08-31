import { CheckCircle, Clock } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import type { LabelingRecord } from '@/features/labeling/types';
import { cn } from '@/lib/cn';

interface LabelingQueueProps { records: LabelingRecord[]; selectedId?: string; onSelect: (id: string) => void }

export function LabelingQueue({ records, selectedId, onSelect }: LabelingQueueProps) {
  const { t, i18n } = useTranslation();
  if (!records.length) return <QueryState state="empty" titleOverride={t('labeling.workbench.noResultsTitle')} descriptionOverride={t('labeling.workbench.noResultsBody')} />;
  return <ul className="divide-y divide-border">{records.map((record) => {
    const selected = record.callId === selectedId;
    const time = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(record.createdAt));
    return <li key={record.callId}><button type="button" aria-current={selected ? 'true' : undefined} onClick={() => onSelect(record.callId)} className={cn('grid w-full gap-2 border-l-2 border-transparent p-4 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus', selected && 'border-secondary bg-info')}>
      <span className="flex min-w-0 items-start justify-between gap-3"><strong className="truncate text-body text-ink">{record.promptTitle} · {record.revisionNumber ? `r${record.revisionNumber}` : t('labeling.metadata.unavailable')}</strong><Tag state={record.label ? 'success' : 'neutral'}>{record.label ? t('labeling.filters.labeled') : t('labeling.filters.unlabeled')}</Tag></span>
      <span className="truncate text-caption text-muted">{record.consumerLabel ?? t('labeling.metadata.unavailable')} · {t(`labeling.outcome.${record.outcome}`)}</span>
      <span className="flex items-center gap-1.5 text-caption text-muted">{record.label ? <CheckCircle className="size-4" weight="fill" /> : <Clock className="size-4" />} {time}</span>
    </button></li>;
  })}</ul>;
}

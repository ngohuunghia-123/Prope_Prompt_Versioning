import { CheckCircle, WarningCircle, XCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import type { LogEntry } from '@/features/prompt-lifecycle/components/logEntryTypes';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface RequestLogTableProps {
  entries: LogEntry[];
  onSelect: (entry: LogEntry) => void;
}

const outcomeIcon = {
  success: <CheckCircle aria-hidden className="size-4 text-success-text" weight="fill" />,
  fallback: <WarningCircle aria-hidden className="size-4 text-warning" weight="fill" />,
  error: <XCircle aria-hidden className="size-4 text-danger-text" weight="fill" />,
};

export function RequestLogTable({ entries, onSelect }: RequestLogTableProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-body">
        <thead><tr className="border-b border-border text-left text-caption font-medium text-muted">
          <th className="pb-3 pr-4">{t('lifecycle.overview.logs.requestId')}</th><th className="pb-3 pr-4">{t('lifecycle.overview.logs.timestamp')}</th><th className="pb-3 pr-4">{t('lifecycle.overview.logs.consumer')}</th><th className="pb-3 pr-4">{t('lifecycle.overview.logs.tokens')}</th><th className="pb-3 pr-4">{t('lifecycle.overview.logs.cost')}</th><th className="pb-3">{t('lifecycle.overview.logs.outcome')}</th>
        </tr></thead>
        <tbody className="divide-y divide-border">
          {entries.map((entry) => {
            const { record } = entry;
            return (
              <tr key={record.id} className="hover:bg-subtle/50">
                <td className="py-3 pr-4"><Button intent="ghost" size="small" className="normal-case tracking-normal" onClick={() => onSelect(entry)}>{record.id}</Button></td>
                <td className="py-3 pr-4 text-ink">{format.date(record.timestamp)}</td>
                <td className="py-3 pr-4 text-ink">{record.consumer}</td>
                <td className="py-3 pr-4 text-ink">{format.number(record.tokens)}</td>
                <td className="py-3 pr-4 text-ink">{format.currency(record.cost)}</td>
                <td className="py-3"><span className={cn('inline-flex items-center gap-1.5 rounded-tag px-2 py-0.5 text-caption font-medium', record.outcome === 'success' ? 'bg-success/10 text-success-text' : record.outcome === 'fallback' ? 'bg-warning/10 text-warning' : 'bg-danger/10 text-danger-text')}>{outcomeIcon[record.outcome]}{t(`lifecycle.overview.logs.outcome${record.outcome[0]?.toUpperCase()}${record.outcome.slice(1)}`)}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

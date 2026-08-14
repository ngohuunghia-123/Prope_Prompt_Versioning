import { CaretRight } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Checkbox } from '@/components/ui/Checkbox';
import { Tag } from '@/components/Tag';
import type { PromptLog } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface PromptLogTableProps {
  logs: PromptLog[];
  selectedId?: string;
  onSelect: (log: PromptLog) => void;
}

export function PromptLogTable({ logs, selectedId, onSelect }: PromptLogTableProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [checkedIds, setCheckedIds] = useState<string[]>([]);
  const toggle = (id: string) => setCheckedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-2xl border-collapse text-left text-body">
        <thead className="bg-subtle text-caption text-muted">
          <tr className="border-b border-border">
            <th className="w-12 px-3 py-3"><span className="sr-only">{t('lifecycle.overview.logs.select')}</span></th>
            {['timestamp', 'technology', 'type', 'descriptionColumn', 'size'].map((key) => <th key={key} className="px-3 py-3 font-semibold">{t(`lifecycle.overview.logs.${key}`)}</th>)}
            <th className="w-12"><span className="sr-only">{t('lifecycle.overview.logs.viewDetail')}</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {logs.map((log) => (
            <tr key={log.id} className={cn('transition-colors hover:bg-subtle/60', selectedId === log.id && 'bg-accent-soft/60')}>
              <td className="px-3 py-3"><Checkbox label={t('lifecycle.overview.logs.selectLog', { id: log.id })} className="[&>span:last-child]:sr-only" checked={checkedIds.includes(log.id)} onChange={() => toggle(log.id)} /></td>
              <td className="whitespace-nowrap px-3 py-3 text-ink">{format.date(log.timestamp)}</td>
              <td className="px-3 py-3"><Tag state="neutral">{log.technology}</Tag></td>
              <td className="px-3 py-3 text-ink">{t(`lifecycle.overview.logs.types.${log.type}`)}</td>
              <td className="max-w-sm px-3 py-3">
                <button type="button" onClick={() => onSelect(log)} className="line-clamp-2 text-left text-ink hover:text-link focus-visible:rounded-control focus-visible:outline-2 focus-visible:outline-focus">{log.description}</button>
              </td>
              <td className="whitespace-nowrap px-3 py-3 text-muted">{t('lifecycle.overview.logs.sizeValue', { size: format.number(log.sizeKb) })}</td>
              <td className="pr-3"><button type="button" onClick={() => onSelect(log)} aria-label={t('lifecycle.overview.logs.viewLog', { id: log.id })} className="grid size-9 place-items-center rounded-full text-muted hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"><CaretRight aria-hidden className="size-4" /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

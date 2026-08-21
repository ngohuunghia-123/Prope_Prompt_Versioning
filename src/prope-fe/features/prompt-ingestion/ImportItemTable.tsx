import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import type { ImportItem } from '@/features/prompt-ingestion/types';

interface ImportItemTableProps {
  items: ImportItem[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onResolution: (item: ImportItem, resolution: 'create' | 'revise' | 'skip') => void;
  updating: boolean;
}

export function ImportItemTable({ items, selected, onToggle, onResolution, updating }: ImportItemTableProps) {
  const { t } = useTranslation();
  if (items.length === 0) return <p className="rounded-card border border-border bg-surface p-6 text-body text-muted">{t('ingestion.review.empty')}</p>;
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface shadow-card">
      <table className="w-full min-w-3xl border-collapse text-left text-body">
        <thead className="bg-subtle text-muted"><tr><th className="p-3">{t('ingestion.review.select')}</th><th className="p-3">{t('ingestion.review.prompt')}</th><th className="p-3">{t('ingestion.review.state')}</th><th className="p-3">{t('ingestion.review.duplicate')}</th><th className="p-3">{t('ingestion.review.resolution')}</th></tr></thead>
        <tbody>
          {items.map((item) => {
            const ready = item.state === 'ready' && item.resolution !== 'skip';
            return <tr key={item.id} className="border-t border-border align-top">
              <td className="p-3"><Button size="icon" intent={selected.has(item.id) ? 'primary' : 'neutral'} disabled={!ready} aria-label={t('ingestion.review.toggle')} onClick={() => onToggle(item.id)}>{selected.has(item.id) ? '✓' : '○'}</Button></td>
              <td className="p-3"><p className="font-semibold text-ink">{item.title}</p><p className="text-caption text-muted">{item.namespace}/{item.name}</p>{item.error_code ? <p className="text-caption text-danger-text">{item.error_code}</p> : null}</td>
              <td className="p-3 text-muted">{t(`ingestion.states.${item.state}`, { defaultValue: item.state })}</td>
              <td className="p-3 text-muted">{item.semantic_matches[0]?.title ?? t('ingestion.review.none')}</td>
              <td className="min-w-44 p-3"><Select label={t('ingestion.review.resolution')} labelHidden value={item.resolution ?? ''} disabled={updating || !['ready', 'skipped'].includes(item.state)} onValueChange={(value) => onResolution(item, value as 'create' | 'revise' | 'skip')} options={[{ value: '', label: t('ingestion.review.choose') }, { value: 'create', label: t('ingestion.review.create') }, { value: 'revise', label: t('ingestion.review.revise'), disabled: !item.target_prompt_id && !item.semantic_matches[0] }, { value: 'skip', label: t('ingestion.review.skip') }]} /></td>
            </tr>;
          })}
        </tbody>
      </table>
    </div>
  );
}

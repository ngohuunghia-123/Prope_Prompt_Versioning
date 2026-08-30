import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import type { Dataset } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface DatasetCardProps { dataset: Dataset; onClick: () => void }

export function DatasetCard({ dataset, onClick }: DatasetCardProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  return (
    <button type="button" onClick={onClick} className="group w-full cursor-pointer rounded-xl border border-border bg-surface p-4 text-left shadow-panel hover:border-focus hover:shadow-elevated focus-visible:outline-2 focus-visible:outline-focus">
      <div className="grid gap-2">
        <h3 className="truncate text-body font-semibold text-ink group-hover:text-link">{dataset.name}</h3>
        <p className="line-clamp-2 text-caption text-muted">{dataset.description}</p>
        <div className="flex flex-wrap gap-1.5">{dataset.tags.map((tag) => <Tag key={tag} state="neutral">{tag}</Tag>)}</div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3 text-caption text-muted">
        <div className="flex items-center gap-3"><span>{t('lifecycle.dataset.fields.testCases')}: <strong className="text-ink">{dataset.testCaseCount}</strong></span><span>{t('lifecycle.dataset.fields.prompts')}: <strong className="text-ink">{dataset.linkedPromptIds.length}</strong></span></div>
        <span>{format.date(dataset.updatedAt)}</span>
      </div>
    </button>
  );
}

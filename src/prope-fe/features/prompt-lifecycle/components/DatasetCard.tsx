import { Lock } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import type { EvalDataset } from '@/features/prompt-lifecycle/evalTypes';

interface DatasetCardProps { dataset: EvalDataset; onClick: () => void }

export function DatasetCard({ dataset, onClick }: DatasetCardProps) {
  const { t } = useTranslation();
  return (
    <button type="button" onClick={onClick} className="group w-full cursor-pointer rounded-xl border border-border bg-surface p-4 text-left shadow-panel hover:border-focus hover:shadow-elevated focus-visible:outline-2 focus-visible:outline-focus">
      <div className="grid gap-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="min-w-0 truncate text-body font-semibold text-ink group-hover:text-link">{dataset.name}</h3>
          {dataset.read_only ? <Lock aria-hidden className="mt-0.5 size-4 shrink-0 text-muted" /> : null}
        </div>
        <p className="line-clamp-2 text-caption text-muted">{dataset.description}</p>
        <div className="flex flex-wrap gap-1.5">
          <Tag state="neutral">{t(`lifecycle.dataset.types.${dataset.kind.replace('-', '')}`)}</Tag>
          {dataset.tags.map((tag) => <Tag key={tag} state="neutral">{tag}</Tag>)}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3 text-caption text-muted">
        <span>{t('lifecycle.evalDatasets.caseCount', { count: dataset.case_count })}</span>
        <span>{dataset.folder === '' ? t('lifecycle.evalDatasets.sharedFolder') : dataset.folder}</span>
      </div>
    </button>
  );
}

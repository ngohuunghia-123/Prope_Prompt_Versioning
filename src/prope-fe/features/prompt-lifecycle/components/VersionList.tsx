import { Check, GitCommit, RocketLaunch } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Tooltip } from '@/components/ui/Tooltip';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface VersionListProps {
  prompt: PromptDetail;
  selectedId: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
}

const statusTone = { inUse: 'active', approved: 'active', retired: 'disabled', inReview: 'pending', draft: 'disabled' } as const;

export function VersionList({ prompt, selectedId, onSelect, onCreate }: VersionListProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  return (
    <aside className="space-y-4">
      <div className="rounded-modal border border-border bg-surface p-4 shadow-panel"><div className="mb-4 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-subtle text-secondary"><GitCommit aria-hidden className="size-5" /></span><div><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.overview.versioning.title')}</h2><p className="text-caption text-muted">{t('lifecycle.overview.versioning.versions', { count: prompt.revisions.length })}</p></div></div><Button className="w-full" size="small" leadingIcon={<RocketLaunch aria-hidden className="size-4" />} onClick={onCreate}>{t('lifecycle.overview.versioning.createNew')}</Button></div>
      <ol className="grid gap-2">{prompt.revisions.map((revision) => (
        <li key={revision.id}><Tooltip className="w-full" side="right" label={revision.summary}><button type="button" aria-pressed={revision.id === selectedId} onClick={() => onSelect(revision.id)} className={cn('w-full rounded-xl border border-transparent p-3 text-left hover:bg-surface focus-visible:outline-2 focus-visible:outline-focus', revision.id === selectedId && 'border-border bg-subtle shadow-inset')}><div className="flex items-center justify-between gap-2"><strong className="text-body text-ink">{revision.number}</strong><StatusBadge tone={statusTone[revision.status]}>{t(`status.${revision.status}`)}</StatusBadge></div><p className="mt-1 line-clamp-2 text-caption text-muted">{revision.summary}</p><p className="mt-2 text-caption text-muted">{format.date(revision.createdAt)}</p><div className="mt-2 flex items-center gap-2 text-caption"><span className="text-success-text"><Check aria-hidden className="mr-1 inline size-3" weight="bold" />{revision.evalPassed}/{revision.evalTotal}</span><span className="text-muted">{format.currency(revision.cost)}</span></div></button></Tooltip></li>
      ))}</ol>
    </aside>
  );
}

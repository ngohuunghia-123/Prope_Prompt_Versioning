import { CheckCircle, GitCommit, RocketLaunch } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

export interface VersionHistoryPanelProps {
  prompt: PromptDetail;
  selectedRevisionId: string;
  onSelectRevision: (revisionId: string) => void;
}

const statusTone = { inUse: 'active', approved: 'active', retired: 'disabled', inReview: 'pending', draft: 'disabled' } as const;

export function VersionHistoryPanel({ prompt, selectedRevisionId, onSelectRevision }: VersionHistoryPanelProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const { userName } = useWorkspaceDisplayNames();
  return (
    <aside aria-labelledby="version-history-title" className="rounded-modal border border-border bg-surface p-4 shadow-panel lg:sticky lg:top-24 lg:self-start sm:p-5">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-subtle text-secondary"><GitCommit aria-hidden className="size-5" /></span>
        <div><h2 id="version-history-title" className="font-display text-heading-3 text-ink">{t('lifecycle.overview.versioning.title')}</h2><p className="mt-1 text-caption text-muted">{t('lifecycle.overview.versioning.description')}</p></div>
      </div>
      <ol className="mt-5 grid gap-2 border-l border-border pl-3">
        {prompt.revisions.map((revision) => {
          const selected = revision.id === selectedRevisionId;
          return (
            <li key={revision.id}>
              <button type="button" aria-pressed={selected} onClick={() => onSelectRevision(revision.id)} className={cn('w-full cursor-pointer rounded-xl border border-transparent p-3 text-left transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus', selected && 'border-border bg-subtle shadow-inset')}>
                <span className="flex items-center justify-between gap-2"><strong className="text-body text-ink">{revision.number}</strong><StatusBadge tone={statusTone[revision.status]}>{t(`status.${revision.status}`)}</StatusBadge></span>
                <span className="mt-2 block text-caption text-muted">{revision.summary}</span>
                <span className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted"><span>{userName(revision.author)}</span><span>{format.date(revision.createdAt)}</span></span>
                <span className="mt-2 flex items-center gap-2 text-caption font-medium text-success-text"><CheckCircle aria-hidden className="size-4" />{t('lifecycle.overview.versioning.evalScore', { passed: revision.evalPassed, total: revision.evalTotal })}</span>
              </button>
            </li>
          );
        })}
      </ol>
      <div className="mt-4 flex items-start gap-2 rounded-xl border border-border bg-subtle p-3 text-caption text-muted"><RocketLaunch aria-hidden className="mt-0.5 size-4 shrink-0 text-secondary" /><p>{t('lifecycle.overview.versioning.releasePointer', { revision: prompt.revision })}</p></div>
    </aside>
  );
}

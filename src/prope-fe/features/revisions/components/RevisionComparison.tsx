import { ArrowLeft, Flask, PencilSimple } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { PromptRevision } from '@/features/revisions/types';
import { useRevisionDiff } from '@/features/revisions/useRevisionDiff';
import { RevisionRuntimeComparison } from '@/features/revisions/components/RevisionRuntimeComparison';
import { cn } from '@/lib/cn';

interface RevisionComparisonProps { promptId: string; current: PromptRevision; earlier: PromptRevision; }

export function RevisionComparison({ promptId, current, earlier }: RevisionComparisonProps) {
  const { t } = useTranslation();
  const { currentDiff, earlierDiff } = useRevisionDiff(current, earlier);
  const panels = [{ revision: earlier, lines: earlierDiff, tone: 'removed' }, { revision: current, lines: currentDiff, tone: 'added' }] as const;
  return (
    <div className="space-y-5">
      <header className="rounded-panel bg-subtle p-5 sm:p-7"><p className="text-overline font-semibold text-muted">{t('revisions.compare.eyebrow')}</p><h1 className="mt-2 text-heading-1 font-semibold">{t('revisions.compare.title', { earlier: earlier.number, current: current.number })}</h1><p className="mt-2 text-body text-muted">{t('revisions.compare.description')}</p></header>
      <div className="grid gap-5 lg:grid-cols-2">
        {panels.map(({ revision, lines, tone }) => <section key={revision.id} className="overflow-hidden rounded-panel border border-border bg-surface shadow-panel"><header className="border-b border-border p-5"><p className="text-overline font-semibold text-muted">{tone === 'added' ? t('revisions.compare.current') : t('revisions.compare.earlier')}</p><h2 className="mt-1 text-heading-3 font-semibold">{t('revisions.version', { number: revision.number })}</h2><p className="mt-1 text-caption text-muted">{revision.summary}</p></header><pre className="min-h-64 whitespace-pre-wrap p-5 font-sans text-body leading-6 text-ink">{lines.map((line, index) => <span key={`${revision.id}-${index}`} className={cn('block px-2', line.changed && (tone === 'added' ? 'bg-success text-success-text' : 'bg-danger text-danger-text'))}>{line.value || ' '}</span>)}</pre></section>)}
      </div>
      <RevisionRuntimeComparison current={current} earlier={earlier} />
      <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><h2 className="text-heading-3 font-semibold">{t('revisions.next.title')}</h2><p className="mt-1 text-body text-muted">{t('revisions.next.description')}</p><div className="mt-5 flex flex-wrap gap-2"><Link to={`/app/prompts/${promptId}/revisions/new`} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-primary px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus"><PencilSimple aria-hidden className="size-4" />{t('revisions.actions.editAgain')}</Link><Link to={`/app/prompts/${promptId}`} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-border bg-surface px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('revisions.actions.keepDraft')}</Link><Link to={`/app/prompts/${promptId}/evaluation`} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-secondary px-4 text-body font-semibold uppercase tracking-button text-inverse shadow-raised focus-visible:outline-2 focus-visible:outline-focus"><Flask aria-hidden className="size-4" />{t('revisions.actions.prepareEvidence')}</Link></div></section>
    </div>
  );
}

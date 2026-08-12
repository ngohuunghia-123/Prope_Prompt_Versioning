import { ArrowRight, ClockCounterClockwise, Flask, PencilSimple } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import type { PromptRevision } from '@/features/revisions/types';
import { RevisionPairSelector } from '@/features/revisions/components/RevisionPairSelector';

interface RevisionHistoryProps { promptId: string; revisions: PromptRevision[]; locale: string; }

export function RevisionHistory({ promptId, revisions, locale }: RevisionHistoryProps) {
  const { t } = useTranslation();
  const current = revisions.find((revision) => revision.isCurrent) ?? revisions[0];
  return (
    <section aria-labelledby="revision-history-title" className="overflow-hidden rounded-panel border border-border bg-surface shadow-floating">
      <header className="flex flex-col gap-4 border-b border-border p-5 sm:flex-row sm:items-end sm:justify-between sm:p-7">
        <div><p className="text-overline font-semibold text-muted">{t('revisions.history.eyebrow')}</p><h1 id="revision-history-title" className="mt-2 text-heading-1 font-semibold">{t('revisions.history.title')}</h1><p className="mt-2 text-body text-muted">{t('revisions.history.description')}</p></div>
        <div className="flex flex-wrap gap-2"><Link to={`/app/prompts/${promptId}/evaluation`} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-border bg-surface px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus"><Flask aria-hidden className="size-4" />{t('revisions.actions.prepareEvidence')}</Link><Link to={`/app/prompts/${promptId}/revisions/new`} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-primary px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus"><PencilSimple aria-hidden className="size-4" />{t('revisions.actions.editAgain')}</Link></div>
      </header>
      <div className="border-b border-border p-5 sm:p-7"><RevisionPairSelector promptId={promptId} revisions={revisions} /></div>
      <ol className="divide-y divide-border">
        {revisions.map((revision) => {
          const formatted = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(revision.createdAt));
          return <li key={revision.id} className="grid gap-4 p-5 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center sm:p-7">
            <span className="grid size-10 place-items-center rounded-full bg-subtle text-secondary"><ClockCounterClockwise aria-hidden className="size-5" /></span>
            <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="text-heading-3 font-semibold">{t('revisions.version', { number: revision.number })}</h2><StatusBadge tone={revision.status === 'approved' ? 'active' : revision.status === 'inReview' ? 'pending' : 'disabled'}>{t(`preservation.status.${revision.status}`)}</StatusBadge>{revision.isCurrent ? <StatusBadge tone="pending">{t('revisions.current')}</StatusBadge> : null}</div><p className="mt-1 text-body text-ink">{revision.summary}</p><p className="mt-2 break-all text-caption text-muted">{t('revisions.history.metadataWithId', { id: revision.id, editor: revision.editorName, date: formatted })}</p></div>
            {!revision.isCurrent && current ? <Link to={`/app/prompts/${promptId}/revisions/compare/${revision.id}`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus">{t('revisions.actions.compare')}<ArrowRight aria-hidden className="size-4" /></Link> : null}
          </li>;
        })}
      </ol>
    </section>
  );
}

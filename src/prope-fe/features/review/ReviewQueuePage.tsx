import { ArrowClockwise, ArrowRight, Clock, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { reviewTaskOptions } from '@/features/review/api';

export function ReviewQueuePage() {
  const { t, i18n } = useTranslation();
  const tasks = useQuery(reviewTaskOptions);
  return <PreservationShell activeId="reviews" title={t('review.queue.pageTitle')} description={t('review.queue.pageDescription')}>
    <div className="mx-auto max-w-content space-y-5">
      {tasks.isPending ? <div className="h-80 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
      {tasks.isError ? <section role="alert" className="grid min-h-80 place-items-center rounded-panel border border-danger-strong bg-danger p-6 text-center"><div><WarningCircle aria-hidden className="mx-auto size-10 text-danger-text" /><h2 className="mt-4 text-heading-2 font-semibold">{t('review.queue.errorTitle')}</h2><p className="mt-2 text-body text-danger-text">{t('review.queue.errorBody')}</p><Button className="mt-5" intent="neutral" leadingIcon={<ArrowClockwise aria-hidden className="size-4" />} onClick={() => void tasks.refetch()}>{t('review.queue.retry')}</Button></div></section> : null}
      {tasks.data?.length === 0 ? <section className="grid min-h-80 place-items-center rounded-panel border border-border bg-surface p-6 text-center"><div><h2 className="text-heading-2 font-semibold">{t('review.queue.emptyTitle')}</h2><p className="mt-2 text-body text-muted">{t('review.queue.emptyBody')}</p></div></section> : null}
      {tasks.data?.length ? <section className="overflow-hidden rounded-panel border border-border bg-surface shadow-floating"><header className="border-b border-border p-5 sm:p-7"><p className="text-overline font-semibold text-muted">{t('review.queue.eyebrow')}</p><h2 className="mt-2 text-heading-1 font-semibold">{t('review.queue.count', { count: tasks.data.length })}</h2></header><ol className="divide-y divide-border">{tasks.data.map((task) => { const created = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(task.createdAt)); const due = task.dueAt ? new Date(task.dueAt) : null; const dueLabel = due ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(due) : ''; const overdue = due ? due.getTime() < Date.now() : false; return <li key={task.id} className="grid gap-4 p-5 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center sm:p-7"><span className="grid size-10 place-items-center rounded-full bg-subtle text-secondary"><Clock aria-hidden className="size-5" /></span><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="text-heading-3 font-semibold">{task.promptTitle}</h3><StatusBadge tone={task.kind === 'breakGlassFollowUp' ? 'error' : 'pending'}>{t(`review.queue.kind.${task.kind}`)}</StatusBadge></div><p className="mt-1 break-all text-caption text-muted">{t('review.queue.metadata', { owner: task.ownerName, revision: task.revisionNumber, id: task.versionId, date: created })}</p>{due ? <p className={`mt-2 text-caption font-semibold ${overdue ? 'text-danger-text' : 'text-muted'}`}>{t(overdue ? 'review.queue.overdue' : 'review.queue.followUpDue', { date: dueLabel })}</p> : null}</div><Link to={`/app/prompts/${task.promptId}/review`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus">{t('review.queue.open')}<ArrowRight aria-hidden className="size-4" /></Link></li>; })}</ol></section> : null}
    </div>
  </PreservationShell>;
}

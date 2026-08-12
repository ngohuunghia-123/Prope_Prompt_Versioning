import { ArrowLeft, ArrowRight, GitDiff, ShieldCheck, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { buttonVariants } from '@/components/ui/buttonVariants';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { reviewOptions, useReviewDecision } from '@/features/review/api';
import { ReviewDecisionForm } from '@/features/review/components/ReviewDecisionForm';
import { ReviewContextPanel } from '@/features/review/components/ReviewContextPanel';
import { ReviewEvidenceSummary } from '@/features/review/components/ReviewEvidenceSummary';
import type { ReviewDecisionFormValues } from '@/features/review/types';

export function ReviewApprovalPage() {
  const { id = '' } = useParams();
  const { t, i18n } = useTranslation();
  const review = useQuery(reviewOptions(id));
  const decision = useReviewDecision();
  const submittedAt = review.data ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(review.data.submittedAt)) : '';
  const decidedAt = review.data?.decision ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(review.data.decision.decidedAt)) : '';
  const submit = (values: ReviewDecisionFormValues) => decision.mutate({ promptId: id, ...values });
  return <PreservationShell activeId="registry" title={t('review.pageTitle')} description={t('review.pageDescription')}>
    <div className="mx-auto max-w-content space-y-5">
      <Link to={`/app/prompts/${id}/evaluation`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('review.actions.back')}</Link>
      {review.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
      {review.isError ? <section role="alert" className="grid min-h-80 place-items-center rounded-panel border border-danger-strong bg-danger p-6 text-center"><div><WarningCircle aria-hidden className="mx-auto size-10 text-danger-text" /><h1 className="mt-4 text-heading-2 font-semibold">{t('review.states.error.title')}</h1><p className="mt-2 text-body text-danger-text">{t('review.states.error.body')}</p></div></section> : null}
      {review.data?.permission === 'denied' ? <section className="grid min-h-80 place-items-center rounded-panel border border-border bg-surface p-6 text-center"><div><ShieldCheck aria-hidden className="mx-auto size-10 text-muted" /><h1 className="mt-4 text-heading-2 font-semibold">{t('review.states.denied.title')}</h1><p className="mt-2 text-body text-muted">{t('review.states.denied.body')}</p></div></section> : null}
      {review.data?.permission === 'review' ? <>
        <header className="overflow-hidden rounded-panel border border-border bg-surface shadow-floating"><div className="bg-hero p-5 text-inverse sm:p-8"><div className="flex flex-wrap items-center gap-2"><StatusBadge tone={review.data.decision?.status === 'approved' ? 'active' : 'pending'}>{review.data.decision ? t(`review.status.${review.data.decision.status}`) : t('review.status.awaiting')}</StatusBadge><span className="text-caption text-inverse/80">{t('revisions.version', { number: review.data.revisionNumber })}</span></div><h1 className="mt-6 text-heading-1 font-semibold sm:text-display-2">{review.data.promptTitle}</h1><p className="mt-3 text-body-large text-inverse/80">{review.data.changeSummary}</p><p className="mt-5 text-caption text-inverse/70">{t('review.hero.submitted', { author: review.data.authorName, date: submittedAt })}</p></div></header>
        <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><div className="flex items-center gap-3"><GitDiff aria-hidden className="size-6 text-secondary" /><div><p className="text-overline font-semibold text-muted">{t('review.diff.eyebrow')}</p><h2 className="mt-1 text-heading-2 font-semibold">{t('review.diff.title')}</h2></div></div><div className="mt-5 grid gap-4 lg:grid-cols-2"><article className="rounded-modal border border-border bg-canvas p-4"><p className="text-caption font-semibold text-muted">{t('review.diff.before')}</p><p className="mt-3 whitespace-pre-wrap text-body text-ink">{review.data.beforeContent}</p></article><article className="rounded-modal border border-success-strong bg-success p-4"><p className="text-caption font-semibold text-success-text">{t('review.diff.candidate')}</p><p className="mt-3 whitespace-pre-wrap text-body text-ink">{review.data.candidateContent}</p></article></div></section>
        <ReviewEvidenceSummary workspace={review.data} />
        <ReviewContextPanel workspace={review.data} />
        {decision.isError ? <Notification className="max-w-none" tone="error" title={t('review.notices.errorTitle')}>{t('review.notices.errorBody')}</Notification> : null}
        {review.data.decision ? <section className="rounded-panel border border-success-strong bg-success p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-success-text">{t('review.record.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t(`review.record.${review.data.decision.status}Title`)}</h2><p className="mt-2 text-body text-success-text">{review.data.decision.reason}</p>{review.data.decision.comment ? <p className="mt-3 rounded-control bg-surface/60 p-3 text-body text-ink">{review.data.decision.comment}</p> : null}<p className="mt-4 text-caption text-muted">{t('review.record.metadata', { reviewer: review.data.decision.reviewerName, date: decidedAt })}</p>{review.data.decision.status === 'approved' ? <Link className={buttonVariants({ intent: 'success', className: 'mt-5' })} to={`/app/prompts/${id}/release`}>{t('review.actions.continueToRelease')}<ArrowRight aria-hidden className="size-4" /></Link> : null}</section> : <ReviewDecisionForm saving={decision.isPending} hasFailures={review.data.suites.some((suite) => suite.failed > 0)} onSubmit={submit} />}
      </> : null}
    </div>
  </PreservationShell>;
}

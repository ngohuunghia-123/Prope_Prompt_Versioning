import { ArrowLeft, ArrowRight, CheckCircle, LockKey, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { buttonVariants } from '@/components/ui/buttonVariants';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { promptDetailOptions } from '@/features/preservation/queries';
import { releaseOptions, useReleaseApprovedRevision } from '@/features/release-control/api';
import { ReleaseDecisionForm } from '@/features/release-control/components/ReleaseDecisionForm';
import { ReleaseHistory } from '@/features/release-control/components/ReleaseHistory';
import type { ReleaseDecisionFormValues } from '@/features/release-control/types';

export function ReleaseApprovedRevisionPage() {
  const { id = '' } = useParams();
  const { t, i18n } = useTranslation();
  const prompt = useQuery(promptDetailOptions(id));
  const release = useQuery(releaseOptions(id));
  const mutation = useReleaseApprovedRevision();
  const approved = prompt.data?.status === 'approved';
  const previouslyReleasedCandidate = release.data?.releases.some((item) => item.current && item.revisionId === release.data.candidateRevisionId) ?? false;
  const approvedAt = release.data ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(release.data.approvedAt)) : '';
  const submit = (values: ReleaseDecisionFormValues) => mutation.mutate({ promptId: id, reason: values.reason, breakGlass: values.breakGlass, approved });
  return <PreservationShell activeId="registry" title={t('release.pageTitle')} description={t('release.pageDescription')}>
    <div className="mx-auto max-w-content space-y-5">
      <Link to={`/app/prompts/${id}/review`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('release.actions.back')}</Link>
      {prompt.isPending || release.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
      {prompt.isError || release.isError ? <section role="alert" className="grid min-h-80 place-items-center rounded-panel border border-danger-strong bg-danger p-6 text-center"><div><WarningCircle aria-hidden className="mx-auto size-10 text-danger-text" /><h1 className="mt-4 text-heading-2 font-semibold">{t('release.states.error.title')}</h1><p className="mt-2 text-body text-danger-text">{t('release.states.error.body')}</p></div></section> : null}
      {release.data?.permission === 'denied' ? <section className="grid min-h-80 place-items-center rounded-panel border border-border bg-surface p-6 text-center"><div><LockKey aria-hidden className="mx-auto size-10 text-muted" /><h1 className="mt-4 text-heading-2 font-semibold">{t('release.states.denied.title')}</h1><p className="mt-2 text-body text-muted">{t('release.states.denied.body')}</p></div></section> : null}
      {prompt.data && release.data?.permission === 'release' ? <>
        <header className="overflow-hidden rounded-panel border border-border bg-surface shadow-floating"><div className="bg-hero p-5 text-inverse sm:p-8"><div className="flex flex-wrap items-center gap-2"><StatusBadge tone={approved ? 'active' : 'pending'}>{approved ? t('release.status.approved') : t('release.status.notApproved')}</StatusBadge><span className="text-caption text-inverse/80">{t('revisions.version', { number: release.data.candidateRevisionNumber })}</span></div><h1 className="mt-6 text-heading-1 font-semibold sm:text-display-2">{prompt.data.title}</h1><p className="mt-3 text-body-large text-inverse/80">{t('release.hero.description')}</p></div></header>
        {approved ? <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><div className="flex items-start gap-4"><span className="grid size-11 shrink-0 place-items-center rounded-full bg-success text-success-text"><CheckCircle aria-hidden className="size-6" weight="fill" /></span><div><p className="text-overline font-semibold text-muted">{t('release.approval.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('release.approval.title')}</h2><p className="mt-2 text-body text-muted">{release.data.approvalReason}</p><p className="mt-3 text-caption text-muted">{t('release.approval.metadata', { approver: release.data.approverName, date: approvedAt })}</p></div></div></section> : null}
        <section className="grid gap-4 lg:grid-cols-3"><article className="rounded-modal border border-border bg-surface p-4"><p className="text-caption text-muted">{t('release.context.versionId')}</p><p className="mt-2 break-all text-body font-semibold">{release.data.candidateRevisionId}</p></article><article className="rounded-modal border border-border bg-surface p-4"><p className="text-caption text-muted">{t('release.context.modelName')}</p><p className="mt-2 break-all text-body font-semibold">{release.data.modelName}</p></article><article className="rounded-modal border border-border bg-surface p-4"><p className="text-caption text-muted">{t('release.context.usage')}</p><p className="mt-2 text-body font-semibold">{release.data.usageContext}</p></article></section>
        {!approved ? <Notification className="max-w-none" tone="info" title={t('release.notices.blockedTitle')}>{t('release.notices.blockedBody')}</Notification> : null}
        {mutation.isError ? <Notification className="max-w-none" tone="error" title={t('release.notices.errorTitle')}>{t('release.notices.errorBody')}</Notification> : null}
        {mutation.isSuccess && previouslyReleasedCandidate ? <Notification className="max-w-none" title={t('release.notices.successTitle')}>{t('release.notices.successBody')}</Notification> : null}
        <ReleaseDecisionForm saving={mutation.isPending} disabled={!approved || previouslyReleasedCandidate} onSubmit={submit} />
        <ReleaseHistory workspace={release.data} />
        <Link className={buttonVariants({ intent: 'neutral' })} to={`/app/prompts/${id}/restore`}>{t('release.actions.openRestore')}<ArrowRight aria-hidden className="size-4" /></Link>
      </> : null}
    </div>
  </PreservationShell>;
}

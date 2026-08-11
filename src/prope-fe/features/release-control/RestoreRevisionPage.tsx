import { ArrowLeft, ShieldWarning, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { Modal } from '@/components/ui/Modal';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { releaseOptions, useRestoreApprovedRevision } from '@/features/release-control/api';
import { ReleaseHistory } from '@/features/release-control/components/ReleaseHistory';
import { RestoreDecisionForm } from '@/features/release-control/components/RestoreDecisionForm';
import type { RestoreDecisionFormValues } from '@/features/release-control/types';

export function RestoreRevisionPage() {
  const { id = '' } = useParams();
  const { t } = useTranslation();
  const workspace = useQuery(releaseOptions(id));
  const restore = useRestoreApprovedRevision();
  const [pendingValues, setPendingValues] = useState<RestoreDecisionFormValues | null>(null);
  const confirm = () => { if (!pendingValues) return; restore.mutate({ promptId: id, ...pendingValues }, { onSuccess: () => setPendingValues(null) }); };
  return <PreservationShell activeId="registry" title={t('restore.pageTitle')} description={t('restore.pageDescription')}>
    <div className="mx-auto max-w-content space-y-5">
      <Link to={`/app/prompts/${id}/release`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('restore.actions.back')}</Link>
      {workspace.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
      {workspace.isError ? <section role="alert" className="grid min-h-80 place-items-center rounded-panel border border-danger-strong bg-danger p-6 text-center"><div><WarningCircle aria-hidden className="mx-auto size-10 text-danger-text" /><h1 className="mt-4 text-heading-2 font-semibold">{t('restore.states.error.title')}</h1><p className="mt-2 text-body text-danger-text">{t('restore.states.error.body')}</p></div></section> : null}
      {workspace.data ? <><header className="rounded-panel border border-warning-strong bg-warning p-5 shadow-floating sm:p-8"><ShieldWarning aria-hidden className="size-9 text-warning-strong" /><p className="mt-5 text-overline font-semibold text-warning-strong">{t('restore.hero.eyebrow')}</p><h1 className="mt-2 text-heading-1 font-semibold text-ink sm:text-display-2">{t('restore.hero.title')}</h1><p className="mt-3 max-w-copy text-body-large text-warning-strong">{t('restore.hero.description')}</p></header>{restore.isError ? <Notification className="max-w-none" tone="error" title={t('restore.notices.errorTitle')}>{t('restore.notices.errorBody')}</Notification> : null}{restore.isSuccess ? <Notification className="max-w-none" title={t('restore.notices.successTitle')}>{t('restore.notices.successBody')}</Notification> : null}<RestoreDecisionForm workspace={workspace.data} saving={restore.isPending} onSubmit={setPendingValues} /><ReleaseHistory workspace={workspace.data} /></> : null}
    </div>
    <Modal open={Boolean(pendingValues)} title={t('restore.confirm.title')} description={t('restore.confirm.description')} confirmLabel={t('restore.actions.restore')} destructive onClose={() => setPendingValues(null)} onConfirm={confirm} />
  </PreservationShell>;
}

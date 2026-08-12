import { ArrowLeft } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { promptDetailOptions } from '@/features/preservation/queries';
import { accessOptions, useGrantAccess, useRevokeAccess, useTransferOwnership, useUpdateAccess } from '@/features/access-management/api';
import { AccessGrantPanel } from '@/features/access-management/components/AccessGrantPanel';
import { AccessDecisionState } from '@/features/access-management/components/AccessDecisionState';
import { AccessActivity } from '@/features/access-management/components/AccessActivity';
import { AccessLevelForm } from '@/features/access-management/components/AccessLevelForm';
import { OwnershipPanel } from '@/features/access-management/components/OwnershipPanel';

type Notice = 'access' | 'transfer' | 'grant' | 'revoke' | 'accessError' | 'transferError' | 'grantError' | 'revokeError' | null;

export function AccessManagementPage() {
  const { id = '' } = useParams();
  const { t } = useTranslation();
  const prompt = useQuery(promptDetailOptions(id));
  const access = useQuery(accessOptions(id));
  const updateAccess = useUpdateAccess();
  const transfer = useTransferOwnership();
  const grant = useGrantAccess();
  const revoke = useRevokeAccess();
  const [notice, setNotice] = useState<Notice>(null);

  return (
    <PreservationShell activeId="registry" title={t('accessManagement.pageTitle')} description={t('accessManagement.pageDescription')}>
      <div className="mx-auto max-w-content space-y-5">
        <Link to={`/app/prompts/${id}`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('accessManagement.actions.returnToPrompt')}</Link>
        {prompt.isPending || access.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
        {access.isError || (prompt.isError && access.data?.permission !== 'denied') ? <AccessDecisionState promptId={id} mode="error" onRetry={() => { void prompt.refetch(); void access.refetch(); }} /> : null}
        {!prompt.isError && !access.isError && access.data === null ? <AccessDecisionState promptId={id} mode="empty" /> : null}
        {access.data?.permission === 'denied' ? <AccessDecisionState promptId={id} mode="denied" /> : null}
        {prompt.data && access.data?.permission === 'manage' ? <>
          <header className="rounded-panel bg-subtle p-5 sm:p-7"><p className="text-overline font-semibold text-muted">{t('accessManagement.prompt.eyebrow')}</p><h1 className="mt-2 text-heading-1 font-semibold">{prompt.data.title}</h1><p className="mt-2 text-body text-muted">{prompt.data.purpose}</p></header>
          {notice ? <Notification tone={notice.endsWith('Error') ? 'error' : 'success'} title={t(`accessManagement.notices.${notice}.title`)} onDismiss={() => setNotice(null)}>{t(`accessManagement.notices.${notice}.body`)}</Notification> : null}
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(18rem,1fr)]">
            <AccessLevelForm key={`${access.data.access}-${access.data.lastActivityAt}`} record={access.data} saving={updateAccess.isPending} onSave={(values) => updateAccess.mutate({ promptId: id, ...values }, { onSuccess: () => setNotice('access'), onError: () => setNotice('accessError') })} />
            <OwnershipPanel key={`${access.data.ownerId}-${access.data.lastActivityAt}`} record={access.data} transferring={transfer.isPending} onTransfer={(values) => transfer.mutate({ promptId: id, ...values }, { onSuccess: () => setNotice('transfer'), onError: () => setNotice('transferError') })} />
          </div>
          <AccessGrantPanel record={access.data} saving={grant.isPending} onGrant={(values) => grant.mutate({ promptId: id, ...values }, { onSuccess: () => setNotice('grant'), onError: () => setNotice('grantError') })} onRevoke={(grantId) => revoke.mutate({ promptId: id, grantId }, { onSuccess: () => setNotice('revoke'), onError: () => setNotice('revokeError') })} />
          <AccessActivity record={access.data} />
        </> : null}
      </div>
    </PreservationShell>
  );
}

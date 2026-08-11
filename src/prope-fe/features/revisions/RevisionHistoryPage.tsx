import { ArrowLeft } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { revisionOptions } from '@/features/revisions/api';
import { RevisionHistory } from '@/features/revisions/components/RevisionHistory';
import { RevisionState } from '@/features/revisions/components/RevisionState';

export function RevisionHistoryPage() {
  const { id = '' } = useParams();
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const workspace = useQuery(revisionOptions(id));
  return <PreservationShell activeId="registry" title={t('revisions.pageTitle')} description={t('revisions.pageDescription')}><div className="mx-auto max-w-content space-y-5"><Link to={`/app/prompts/${id}`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('revisions.actions.returnToPrompt')}</Link>{location.state?.saved ? <Notification title={t('revisions.saved.title')}>{t('revisions.saved.body')}</Notification> : null}{workspace.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}{workspace.isError ? <RevisionState mode="error" promptId={id} onRetry={() => void workspace.refetch()} /> : null}{workspace.data?.permission === 'denied' ? <RevisionState mode="denied" promptId={id} /> : null}{workspace.data?.permission === 'edit' && workspace.data.revisions.length === 0 ? <RevisionState mode="empty" promptId={id} /> : null}{workspace.data?.permission === 'edit' && workspace.data.revisions.length > 0 ? <RevisionHistory promptId={id} revisions={workspace.data.revisions} locale={i18n.language} /> : null}</div></PreservationShell>;
}

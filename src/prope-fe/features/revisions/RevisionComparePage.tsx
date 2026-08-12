import { ArrowLeft } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { revisionOptions } from '@/features/revisions/api';
import { RevisionComparison } from '@/features/revisions/components/RevisionComparison';
import { RevisionState } from '@/features/revisions/components/RevisionState';

export function RevisionComparePage() {
  const { id = '', revisionId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const workspace = useQuery(revisionOptions(id));
  const current = workspace.data?.revisions.find((revision) => revision.id === (searchParams.get('to') ?? '')) ?? workspace.data?.revisions.find((revision) => revision.isCurrent);
  const earlier = workspace.data?.revisions.find((revision) => revision.id === revisionId && revision.id !== current?.id);
  return <PreservationShell activeId="registry" title={t('revisions.compare.pageTitle')} description={t('revisions.compare.pageDescription')}><div className="mx-auto max-w-content space-y-5"><Link to={`/app/prompts/${id}/revisions`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('revisions.actions.backToHistory')}</Link>{workspace.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}{workspace.isError || (workspace.data && (!current || !earlier)) ? <RevisionState mode="error" promptId={id} onRetry={() => void workspace.refetch()} /> : null}{workspace.data?.permission === 'denied' ? <RevisionState mode="denied" promptId={id} /> : null}{workspace.data?.permission === 'edit' && current && earlier ? <RevisionComparison promptId={id} current={current} earlier={earlier} /> : null}</div></PreservationShell>;
}

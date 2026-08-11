import { ArrowLeft } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { promptDetailOptions } from '@/features/preservation/queries';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { revisionOptions, useSaveRevision } from '@/features/revisions/api';
import { RevisionEditorForm } from '@/features/revisions/components/RevisionEditorForm';
import { RevisionState } from '@/features/revisions/components/RevisionState';

export function RevisionEditorPage() {
  const { id = '' } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const prompt = useQuery(promptDetailOptions(id));
  const workspace = useQuery(revisionOptions(id));
  const save = useSaveRevision();
  const failed = prompt.isError || workspace.isError;
  const current = workspace.data?.revisions[0];
  const initialValues = prompt.data ? {
    content: current?.content ?? prompt.data.content,
    providerName: current?.providerName ?? prompt.data.providerName,
    upstreamModel: current?.upstreamModel ?? prompt.data.upstreamModel,
    temperature: current?.temperature ?? prompt.data.temperature,
    maxTokens: current?.maxTokens ?? prompt.data.maxTokens,
    fallbackAnswer: current?.fallbackAnswer ?? prompt.data.fallbackAnswer,
  } : null;
  return <PreservationShell activeId="registry" title={t('revisions.editor.pageTitle')} description={t('revisions.editor.pageDescription')}><div className="mx-auto max-w-content space-y-5"><Link to={`/app/prompts/${id}`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('revisions.actions.returnToPrompt')}</Link>{prompt.isPending || workspace.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}{failed ? <RevisionState mode="error" promptId={id} onRetry={() => { void prompt.refetch(); void workspace.refetch(); }} /> : null}{workspace.data?.permission === 'denied' ? <RevisionState mode="denied" promptId={id} /> : null}{save.isError ? <Notification tone="error" title={t('revisions.saveFailed.title')}>{t('revisions.saveFailed.body')}</Notification> : null}{initialValues && workspace.data?.permission === 'edit' ? <RevisionEditorForm promptId={id} initialValues={initialValues} saving={save.isPending} onSave={(values) => save.mutate({ promptId: id, ...values }, { onSuccess: () => navigate(`/app/prompts/${id}/revisions`, { state: { saved: true } }) })} /> : null}</div></PreservationShell>;
}

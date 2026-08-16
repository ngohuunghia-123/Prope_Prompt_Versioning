import { useQuery } from '@tanstack/react-query';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { Navigate, useParams } from 'react-router-dom';
import { PromptEditorForm } from '@/features/prompt-lifecycle/components/PromptEditorForm';
import { NewPromptComposer } from '@/features/prompt-lifecycle/NewPromptComposer';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import { AUTHORED_SOURCE, type PromptDetail, type PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { isValidSlug } from '@/lib/slugify';

function getNewPromptValues(t: TFunction, namespace: string): PromptEditorValues {
  return {
    title: t('lifecycle.newPrompt.untitled'),
    // The folder decides the namespace; the name is folded from the title as it
    // is typed, so it starts empty rather than at a placeholder somebody has to
    // notice and clear.
    namespace,
    name: '',
    access: 'private',
    providerConfigId: '',
    upstreamModel: '',
    promptBody: t('lifecycle.newPrompt.defaultBody'),
    fallbackAnswer: t('lifecycle.newPrompt.defaultFallback'),
    changeSummary: t('lifecycle.newPrompt.defaultSummary'),
    // Nothing imported yet. `sourceMode` is derived from here on — the Import
    // panel sets it by loading a source and clears it by removing one — so
    // `authored` is the resting state rather than a tab somebody chose.
    sourceMode: 'authored',
    sourceText: '',
    sourceFormat: 'txt',
  };
}

function valuesFromPrompt(prompt: PromptDetail): PromptEditorValues {
  // Editing an existing revision is always the authored path: there is a body
  // already and nothing to import. The model name is split back apart for
  // display only — both halves are immutable here.
  const [namespace = '', name = ''] = prompt.modelName.split('/');
  return { ...AUTHORED_SOURCE, title: prompt.title, namespace, name, access: prompt.access, providerConfigId: prompt.provider, upstreamModel: prompt.providerModel, promptBody: prompt.promptBody, fallbackAnswer: prompt.fallbackAnswer, changeSummary: '' };
}

export function PromptEditorPage() {
  const { t } = useTranslation();
  const { promptId, folderId } = useParams();
  const query = useQuery({ ...promptOptions(promptId ?? ''), enabled: Boolean(promptId) });

  if (!promptId) {
    // A folder slug that the registry could never have issued cannot be a
    // namespace either, so there is nothing to compose against. Back to the grid
    // rather than a composer whose prefix would 422 on save.
    if (!folderId || !isValidSlug(folderId)) return <Navigate to="/app/prompts" replace />;
    // No promptId to pass: the import flow creates the prompt and routes to
    // whatever id the registry answered with.
    return <NewPromptComposer initialValues={getNewPromptValues(t, folderId)} />;
  }

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;
  return <PromptEditorForm initialValues={valuesFromPrompt(query.data)} promptId={promptId} editing />;
}

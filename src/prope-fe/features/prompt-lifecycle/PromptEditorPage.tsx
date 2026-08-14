import { useQuery } from '@tanstack/react-query';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { useLocation, useParams } from 'react-router-dom';
import { PromptEditorForm } from '@/features/prompt-lifecycle/components/PromptEditorForm';
import { NewPromptComposer } from '@/features/prompt-lifecycle/NewPromptComposer';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import { AUTHORED_SOURCE, promptSuggestionSchema, type PromptDetail, type PromptEditorValues } from '@/features/prompt-lifecycle/types';

function getNewPromptValues(t: TFunction): PromptEditorValues {
  return {
  title: t('lifecycle.newPrompt.untitled'),
  modelName: 'workspace/untitled-prompt',
  access: 'private',
  provider: 'openai',
  providerModel: 'gpt-5.2',
  promptBody: t('lifecycle.newPrompt.defaultBody'),
  fallbackAnswer: t('lifecycle.newPrompt.defaultFallback'),
  changeSummary: t('lifecycle.newPrompt.defaultSummary'),
  // Most people arrive holding a prompt already, so the import tab opens selected.
  sourceMode: 'existing',
  sourceText: '',
  sourceFormat: 'txt',
};
}

function valuesFromPrompt(prompt: PromptDetail): PromptEditorValues {
  // Editing an existing revision is always the authored path: there is a body
  // already and nothing to import.
  return { ...AUTHORED_SOURCE, title: prompt.title, modelName: prompt.modelName, access: prompt.access, provider: prompt.provider.toLowerCase(), providerModel: prompt.providerModel, promptBody: prompt.promptBody, fallbackAnswer: prompt.fallbackAnswer, changeSummary: '' };
}

export function PromptEditorPage() {
  const { t } = useTranslation();
  const { promptId } = useParams();
  const location = useLocation();
  const query = useQuery({ ...promptOptions(promptId ?? ''), enabled: Boolean(promptId) });
  const suggestionResult = promptSuggestionSchema.safeParse((location.state as { suggestion?: unknown } | null)?.suggestion);
  const suggestion = suggestionResult.success ? suggestionResult.data : undefined;
  const newPromptValues = getNewPromptValues(t);
  // Arriving from the wizard means a body was generated already, so the screen
  // opens on the tab that shows it rather than on an empty import form.
  const suggestedValues: PromptEditorValues = suggestion ? {
    ...newPromptValues,
    sourceMode: 'authored',
    title: suggestion.title,
    modelName: `generated/${suggestion.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}`,
    provider: suggestion.model.split('/')[0] ?? newPromptValues.provider,
    providerModel: suggestion.model.split('/')[1] ?? suggestion.model,
    promptBody: suggestion.promptBody,
  } : newPromptValues;
  // No promptId to pass: the import flow creates the prompt and routes to
  // whatever id the registry answered with.
  if (!promptId) return <NewPromptComposer initialValues={suggestedValues} />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;
  return <PromptEditorForm initialValues={valuesFromPrompt(query.data)} promptId={promptId} editing />;
}

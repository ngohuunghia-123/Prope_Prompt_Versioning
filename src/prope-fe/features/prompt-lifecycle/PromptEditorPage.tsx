import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { PromptEditorForm } from '@/features/prompt-lifecycle/components/PromptEditorForm';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import type { PromptDetail, PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { useWorkspaceId } from '@/features/prompt-lifecycle/useWorkspaceId';

const newPromptValues: PromptEditorValues = {
  title: '',
  modelName: '',
  access: 'private',
  provider: '',
  providerModel: '',
  promptBody: '<system>\nYou are a helpful assistant.\n</system>\n\n<context>\nCustomer: {{customer_name}}\n</context>\n\n<instructions>\nAnalyze {{question}} and recommend the next action.\n</instructions>\n\n<output_format>\nReturn valid JSON.\n</output_format>',
  fallbackAnswer: 'Support is temporarily unavailable. Please try again shortly.',
  changeSummary: 'Initial prompt registration.',
};

function valuesFromPrompt(prompt: PromptDetail): PromptEditorValues {
  return {
    title: prompt.title,
    modelName: prompt.modelName,
    access: prompt.access,
    // The provider is a `pvc_...` configuration id, not a brand name — a
    // workspace can configure the same brand twice with different credentials, so
    // the id is what a revision binds to.
    provider: prompt.provider,
    providerModel: prompt.providerModel,
    promptBody: prompt.promptBody,
    fallbackAnswer: prompt.fallbackAnswer,
    // **Always empty on an edit.** The change summary describes *this* change and
    // is what the reviewer reads first; carrying the previous one forward would
    // put a stale sentence in front of every review.
    changeSummary: '',
  };
}

export function PromptEditorPage() {
  const { promptId } = useParams();
  const workspaceId = useWorkspaceId();
  const query = useQuery({
    ...promptOptions(workspaceId, promptId ?? ''),
    enabled: Boolean(workspaceId && promptId),
  });
  // Registering rather than revising: there is no prompt yet, so `POST /prompts`
  // creates the property and its first revision.
  if (!promptId) return <PromptEditorForm initialValues={newPromptValues} promptId={null} />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;
  return <PromptEditorForm initialValues={valuesFromPrompt(query.data)} promptId={promptId} editing />;
}

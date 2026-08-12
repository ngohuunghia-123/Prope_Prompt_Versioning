import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { PromptEditorForm } from '@/features/prompt-lifecycle/components/PromptEditorForm';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import type { PromptDetail, PromptEditorValues } from '@/features/prompt-lifecycle/types';

const newPromptValues: PromptEditorValues = {
  title: '',
  modelName: '',
  access: 'private',
  provider: 'openai',
  providerModel: 'gpt-5.2',
  promptBody: '<system>\nYou are a helpful assistant.\n</system>\n\n<context>\nCustomer: {{customer_name}}\n</context>\n\n<instructions>\nAnalyze {{question}} and recommend the next action.\n</instructions>\n\n<output_format>\nReturn valid JSON.\n</output_format>',
  fallbackAnswer: 'Support is temporarily unavailable. Please try again shortly.',
  changeSummary: 'Initial prompt registration.',
};

function valuesFromPrompt(prompt: PromptDetail): PromptEditorValues {
  return { title: prompt.title, modelName: prompt.modelName, access: prompt.access, provider: prompt.provider.toLowerCase(), providerModel: prompt.providerModel, promptBody: prompt.promptBody, fallbackAnswer: prompt.fallbackAnswer, changeSummary: '' };
}

export function PromptEditorPage() {
  const { promptId } = useParams();
  const query = useQuery({ ...promptOptions(promptId ?? ''), enabled: Boolean(promptId) });
  if (!promptId) return <PromptEditorForm initialValues={newPromptValues} promptId="checkout-assistant" />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;
  return <PromptEditorForm initialValues={valuesFromPrompt(query.data)} promptId={promptId} editing />;
}

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStartEvaluationMutation, useRunPromptTestMutation } from '@/features/prompt-lifecycle/queries';
import { extractTemplateTokens } from '@/features/prompt-lifecycle/xmlBlocks';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

export function usePromptTestWorkbench(promptId: string, prompt: PromptEditorValues) {
  const navigate = useNavigate();
  const variables = useMemo(
    () => extractTemplateTokens(prompt.promptBody).map((token) => token.slice(2, -2).trim()),
    [prompt.promptBody],
  );
  const [inputPrompt, setInputPrompt] = useState('');
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(variables.map((variable) => [variable, ''])),
  );
  const [model, setModel] = useState(prompt.upstreamModel);
  const testMutation = useRunPromptTestMutation();
  const evaluationMutation = useStartEvaluationMutation(promptId);

  const runTest = () => {
    testMutation.mutate({
      promptId,
      promptBody: prompt.promptBody,
      inputPrompt: inputPrompt.trim(),
      model,
      variables: values,
    });
  };

  const startEvaluation = () => {
    evaluationMutation.mutate(prompt, {
      onSuccess: () => void navigate(`/app/prompts/${promptId}/evaluation/run`, { state: { promptDraft: prompt } }),
    });
  };

  return {
    variables,
    inputPrompt,
    setInputPrompt,
    values,
    setVariableValue: (name: string, value: string) => setValues((current) => ({ ...current, [name]: value })),
    model,
    setModel,
    testMutation,
    evaluationMutation,
    canRun: Boolean(inputPrompt.trim()) && variables.every((variable) => Boolean(values[variable]?.trim())),
    runTest,
    startEvaluation,
  };
}

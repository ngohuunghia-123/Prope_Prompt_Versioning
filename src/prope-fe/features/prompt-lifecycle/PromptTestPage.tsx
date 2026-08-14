import { ArrowRight, Play } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { PromptTestCostPanel } from '@/features/prompt-lifecycle/components/PromptTestCostPanel';
import { PromptTestInputPanel } from '@/features/prompt-lifecycle/components/PromptTestInputPanel';
import { PromptTestOutputPanel } from '@/features/prompt-lifecycle/components/PromptTestOutputPanel';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptOptions, providersOptions } from '@/features/prompt-lifecycle/queries';
import { AUTHORED_SOURCE, promptEditorSchema, type PromptDetail, type PromptEditorValues, type Provider } from '@/features/prompt-lifecycle/types';
import { usePromptTestWorkbench } from '@/features/prompt-lifecycle/usePromptTestWorkbench';

function toEditorValues(prompt: PromptDetail): PromptEditorValues {
  return {
    ...AUTHORED_SOURCE,
    title: prompt.title,
    modelName: prompt.modelName,
    access: prompt.access,
    provider: prompt.provider.toLowerCase(),
    providerModel: prompt.providerModel,
    promptBody: prompt.promptBody,
    fallbackAnswer: prompt.fallbackAnswer,
    changeSummary: prompt.purpose,
  };
}

export function PromptTestPage() {
  const { promptId = 'checkout-assistant' } = useParams();
  const location = useLocation();
  const draftResult = promptEditorSchema.safeParse((location.state as { promptDraft?: unknown } | null)?.promptDraft);
  const draft = draftResult.success ? draftResult.data : undefined;
  const promptQuery = useQuery({ ...promptOptions(promptId), enabled: !draft });
  const providersQuery = useQuery(providersOptions);
  const prompt = draft ?? (promptQuery.data ? toEditorValues(promptQuery.data) : undefined);

  if (!draft && promptQuery.isPending) return <QueryState state="loading" />;
  if (!draft && promptQuery.isError) return <QueryState state="error" onRetry={() => void promptQuery.refetch()} />;
  if (!prompt) return <QueryState state="empty" />;

  return <PromptTestWorkbench promptId={promptId} prompt={prompt} providers={providersQuery.data} />;
}

interface PromptTestWorkbenchProps {
  promptId: string;
  prompt: PromptEditorValues;
  providers?: Provider[];
}

function PromptTestWorkbench({ promptId, prompt, providers }: PromptTestWorkbenchProps) {
  const { t } = useTranslation();
  const workbench = usePromptTestWorkbench(promptId, prompt);
  const modelOptions = useMemo(() => {
    const options = providers?.flatMap((provider) => provider.models.map((model) => ({ value: model, label: `${provider.name} · ${model}` }))) ?? [];
    return options.some((option) => option.value === workbench.model)
      ? options
      : [{ value: workbench.model, label: `${prompt.provider} · ${workbench.model}` }, ...options];
  }, [prompt.provider, providers, workbench.model]);

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-6 pb-20">
      {workbench.evaluationMutation.isError ? (
        <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.editor.evaluationError')}</Notification>
      ) : null}
      <div className="grid items-stretch gap-6 lg:grid-cols-[minmax(18rem,0.9fr)_minmax(0,1.35fr)]">
        <PromptTestInputPanel
          inputPrompt={workbench.inputPrompt}
          variables={workbench.variables}
          values={workbench.values}
          onInputPromptChange={workbench.setInputPrompt}
          onVariableChange={workbench.setVariableValue}
        />
        <div className="flex min-w-0 flex-col gap-6">
          <PromptTestCostPanel result={workbench.testMutation.data} />
          <div className="grid gap-3 rounded-modal border border-border bg-surface p-4 shadow-panel sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <Select label={t('lifecycle.promptTest.modelLabel')} options={modelOptions} value={workbench.model} onValueChange={workbench.setModel} />
            <Button className="disabled:bg-disabled disabled:text-disabled-text" type="button" leadingIcon={<Play aria-hidden className="size-4" />} loading={workbench.testMutation.isPending} disabled={!workbench.canRun} onClick={workbench.runTest}>
              {t('lifecycle.promptTest.runTest')}
            </Button>
          </div>
          <PromptTestOutputPanel result={workbench.testMutation.data} pending={workbench.testMutation.isPending} error={workbench.testMutation.isError} />
        </div>
      </div>
      <div className="flex justify-end sm:sticky sm:bottom-4 sm:z-20">
        <div className="rounded-full border border-border bg-canvas/95 p-1 shadow-floating backdrop-blur-sm">
          <Button type="button" trailingIcon={<ArrowRight aria-hidden className="size-4" />} loading={workbench.evaluationMutation.isPending} onClick={workbench.startEvaluation}>
            {t('lifecycle.promptTest.evaluate')}
          </Button>
        </div>
      </div>
    </div>
  );
}

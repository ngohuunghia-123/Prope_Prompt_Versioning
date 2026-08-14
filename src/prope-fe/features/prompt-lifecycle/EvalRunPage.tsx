import { useQuery } from '@tanstack/react-query';
import { Check } from '@phosphor-icons/react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { EvalDatasetList } from '@/features/prompt-lifecycle/components/EvalDatasetList';
import { EvalSummary } from '@/features/prompt-lifecycle/components/EvalSummary';
import { EvalTestDetail } from '@/features/prompt-lifecycle/components/EvalTestDetail';
import { EvalTestList } from '@/features/prompt-lifecycle/components/EvalTestList';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { evalWorkspaceOptions, promptOptions, useCreateEvaluationDatasetWithAiMutation, useRunEvaluationDatasetMutation } from '@/features/prompt-lifecycle/queries';
import { AUTHORED_SOURCE, promptEditorSchema, type PromptDetail, type PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { useEvalWorkspaceSelection } from '@/features/prompt-lifecycle/useEvalWorkspaceSelection';

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

export function EvalRunPage() {
  const { t } = useTranslation();
  const { promptId = 'checkout-assistant' } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const draftResult = promptEditorSchema.safeParse((location.state as { promptDraft?: unknown } | null)?.promptDraft);
  const draft = draftResult.success ? draftResult.data : undefined;
  const promptQuery = useQuery({ ...promptOptions(promptId), enabled: !draft });
  const prompt = draft ?? (promptQuery.data ? toEditorValues(promptQuery.data) : undefined);
  const workspaceQuery = useQuery({ ...evalWorkspaceOptions(promptId, prompt?.promptBody ?? ''), enabled: Boolean(prompt) });
  const runDataset = useRunEvaluationDatasetMutation(promptId, prompt?.promptBody ?? '');
  const createDataset = useCreateEvaluationDatasetWithAiMutation(promptId, prompt?.promptBody ?? '');
  const selection = useEvalWorkspaceSelection(workspaceQuery.data?.datasets ?? []);

  if (!draft && promptQuery.isPending) return <QueryState state="loading" />;
  if (!draft && promptQuery.isError) return <QueryState state="error" onRetry={() => void promptQuery.refetch()} />;
  if (workspaceQuery.isPending) return <QueryState state="loading" />;
  if (workspaceQuery.isError) return <QueryState state="error" onRetry={() => void workspaceQuery.refetch()} />;
  if (!prompt || !workspaceQuery.data || !selection.dataset || !selection.test) return <QueryState state="empty" />;

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-4">
      {runDataset.isError ? (
        <Notification tone="error" title={t('lifecycle.evalWorkspace.runError')}>{t('lifecycle.evalWorkspace.runErrorHint')}</Notification>
      ) : null}
      {createDataset.isError ? (
        <Notification tone="error" title={t('lifecycle.evalWorkspace.createError')}>{t('lifecycle.evalWorkspace.createErrorHint')}</Notification>
      ) : null}
      <div className="grid min-h-dvh gap-4 lg:grid-cols-[minmax(16rem,0.72fr)_minmax(0,2fr)] lg:grid-rows-[auto_minmax(0,1fr)]">
        <div className="min-h-72 lg:row-span-2">
          <EvalDatasetList
            datasets={workspaceQuery.data.datasets}
            selectedId={selection.datasetId}
            runningId={runDataset.isPending ? runDataset.variables : undefined}
            creating={createDataset.isPending}
            onSelect={selection.setDatasetId}
            onCreateWithAi={() => createDataset.mutate(undefined, { onSuccess: (dataset) => selection.setDatasetId(dataset.id) })}
            onRun={(datasetId) => {
              selection.setDatasetId(datasetId);
              runDataset.mutate(datasetId);
            }}
          />
        </div>
        <EvalSummary datasets={workspaceQuery.data.datasets} selectedDataset={selection.dataset} />
        <div className="grid min-h-0 overflow-hidden rounded-modal border border-border bg-surface shadow-panel lg:grid-cols-[minmax(14rem,0.62fr)_minmax(0,1.38fr)]">
          <EvalTestList tests={selection.dataset.tests} selectedId={selection.testId} onSelect={selection.setTestId} />
          <div className="min-h-0 min-w-0 overflow-y-auto"><EvalTestDetail test={selection.test} /></div>
        </div>
      </div>
      <div className="flex justify-end sm:sticky sm:bottom-4 sm:z-20">
        <div className="rounded-full border border-border bg-canvas/95 p-1 shadow-floating backdrop-blur-sm">
          <Button type="button" trailingIcon={<Check aria-hidden className="size-4" weight="bold" />} onClick={() => void navigate(`/app/prompts/${promptId}`)}>
            {t('lifecycle.evalWorkspace.complete')}
          </Button>
        </div>
      </div>
    </div>
  );
}

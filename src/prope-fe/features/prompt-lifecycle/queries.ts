import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  decideReview,
  createEvaluationDatasetWithAi,
  deleteDataset,
  fetchWorkspaceStats,
  generatePromptSuggestions,
  generateSDKKey,
  getAllTraces,
  getCallRecords,
  getConnectedProducts,
  getDataset,
  getDatasets,
  getEditorSuggestions,
  getEvalRun,
  getEvaluationOverview,
  getEvalWorkspace,
  getEvalTrends,
  getEvaluationWorkflow,
  getFolders,
  getPlaygroundRuns,
  getProductionStats,
  getProductionOverview,
  getPrompt,
  getPromptLogs,
  getPrompts,
  getPromptsByFolder,
  getPromptDiff,
  getProviders,
  getReview,
  getReviews,
  getSDKKeys,
  getWizardSteps,
  promoteRevision,
  improvePromptWithAi,
  releaseRevision,
  revokeSDKKey,
  rollbackToRevision,
  runEvalSuite,
  runEvaluationDataset,
  runPlaygroundComparison,
  runPromptTest,
  saveDataset,
  savePrompt,
  saveProvider,
  startEvaluation,
  submitWorkflowAction,
  searchPrompts,
  getPromptIndexStatus,
  getPromptIndexJob,
  triggerPromptIndex,
  deletePromptIndex,
  findSimilarPromptsForImport,
  importPrompt,
  type PromptFilterQuery,
} from '@/features/prompt-lifecycle/api';
import { createEvaluationWorkflow } from '@/features/prompt-lifecycle/workflowData';
import { applyWorkflowAction } from '@/features/prompt-lifecycle/workflowTransitions';
import type { EvalDatasetResult, EvalRun, EvalWorkspace, EvaluationWorkflow, PlaygroundRun, PromoteEnvironment, Prompt, PromptTestInput, WizardAnswers } from '@/features/prompt-lifecycle/types';

export const lifecycleKeys = {
  prompts: ['lifecycle', 'prompts'] as const,
  prompt: (id: string) => ['lifecycle', 'prompt', id] as const,
  reviews: ['lifecycle', 'reviews'] as const,
  review: (id: string) => ['lifecycle', 'review', id] as const,
  providers: ['lifecycle', 'providers'] as const,
  calls: ['lifecycle', 'calls'] as const,
  callsPrompt: (id: string) => ['lifecycle', 'calls', 'prompt', id] as const,
  workflow: (id: string) => ['lifecycle', 'workflow', id] as const,
  playground: (id: string) => ['lifecycle', 'playground', id] as const,
  evalRun: (id: string) => ['lifecycle', 'evalRun', id] as const,
  evalRunLatest: (id: string) => ['lifecycle', 'evalRun', 'latest', id] as const,
  evaluationOverview: (promptId: string, revisionId: string) => ['lifecycle', 'evaluationOverview', promptId, revisionId] as const,
  evalWorkspace: (id: string, promptBody: string) => ['lifecycle', 'evalWorkspace', id, promptBody] as const,
  productionStats: (id: string) => ['lifecycle', 'productionStats', id] as const,
  editorSuggestions: ['lifecycle', 'editorSuggestions'] as const,
  promptDiff: (id: string, revA: string, revB: string) => ['lifecycle', 'diff', id, revA, revB] as const,
  datasets: ['lifecycle', 'datasets'] as const,
  dataset: (id: string) => ['lifecycle', 'dataset', id] as const,
  workspaceStats: ['lifecycle', 'workspaceStats'] as const,
  folders: ['lifecycle', 'folders'] as const,
  search: (query: string, type: 'quick' | 'ai') => ['lifecycle', 'search', type, query] as const,
  promptIndex: (promptId: string) => ['lifecycle', 'prompt-index', promptId] as const,
  indexJob: (jobId: string) => ['lifecycle', 'prompt-index-job', jobId] as const,
};

export const promptsOptions = queryOptions({ queryKey: lifecycleKeys.prompts, queryFn: getPrompts, staleTime: 60_000 });
export const promptOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.prompt(id), queryFn: () => getPrompt(id), staleTime: 60_000 });

export function useAiPromptEditMutation() {
  return useMutation({ mutationFn: improvePromptWithAi });
}
export const reviewsOptions = queryOptions({ queryKey: lifecycleKeys.reviews, queryFn: getReviews, staleTime: 60_000 });
export const reviewOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.review(id), queryFn: () => getReview(id), staleTime: 60_000 });
export const providersOptions = queryOptions({ queryKey: lifecycleKeys.providers, queryFn: getProviders, staleTime: 60_000 });
export const callRecordsOptions = queryOptions({ queryKey: lifecycleKeys.calls, queryFn: getCallRecords, staleTime: 30_000 });
export const workflowOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.workflow(id), queryFn: () => getEvaluationWorkflow(id), staleTime: 60_000, refetchInterval: (query) => query.state.data?.currentStepId === 'LoadContext' ? 800 : false });

export const playgroundOptions = (promptId: string) => queryOptions({
  queryKey: lifecycleKeys.playground(promptId),
  queryFn: () => getPlaygroundRuns(promptId),
  staleTime: 30_000,
});

export const evalRunOptions = (promptId: string) => queryOptions({
  queryKey: lifecycleKeys.evalRunLatest(promptId),
  queryFn: () => getEvalRun(promptId),
  staleTime: 30_000,
});

export const evaluationOverviewOptions = (promptId: string, revisionId: string) => queryOptions({
  queryKey: lifecycleKeys.evaluationOverview(promptId, revisionId),
  queryFn: () => getEvaluationOverview(promptId, revisionId),
  staleTime: 30_000,
});

export const evalWorkspaceOptions = (promptId: string, promptBody: string) => queryOptions({
  queryKey: lifecycleKeys.evalWorkspace(promptId, promptBody),
  queryFn: () => getEvalWorkspace(promptId, promptBody),
  staleTime: 30_000,
});

export const productionStatsOptions = (promptId: string) => queryOptions({
  queryKey: lifecycleKeys.productionStats(promptId),
  queryFn: () => getProductionStats(promptId),
  staleTime: 30_000,
});

export const editorSuggestionsOptions = (promptBody: string) => queryOptions({
  queryKey: [...lifecycleKeys.editorSuggestions, promptBody.length] as const,
  queryFn: () => getEditorSuggestions(promptBody),
  staleTime: 60_000,
});

export const promptLogsOptions = (promptId: string) => queryOptions({
  queryKey: lifecycleKeys.callsPrompt(promptId),
  queryFn: () => getPromptLogs(promptId),
  staleTime: 30_000,
});

export const promptDiffOptions = (promptId: string, revisionA: string, revisionB: string) => queryOptions({
  queryKey: lifecycleKeys.promptDiff(promptId, revisionA, revisionB),
  queryFn: () => getPromptDiff(promptId, revisionA, revisionB),
  staleTime: 60_000,
});

export function useSavePromptMutation() { const client = useQueryClient(); return useMutation({ mutationFn: savePrompt, onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.prompts }) }); }

// ---- Import ----------------------------------------------------------------
// The duplicate check is a mutation rather than a query because it is an act the
// person takes by pressing a button, not a fact about the screen: caching it
// under the body's text would answer the second press with the first press's
// result, which is exactly wrong after they edited the prompt in between.
export function useFindSimilarPromptsMutation() {
  return useMutation({ mutationFn: (text: string) => findSimilarPromptsForImport(text, 3) });
}

export function useImportPromptMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: importPrompt,
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(result.promptId) });
      // A new revision changes the folder listings the registry screen reads.
      void client.invalidateQueries({ queryKey: ['lifecycle', 'folderPrompts'] });
    },
  });
}
export function useStartEvaluationMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: startEvaluation, onSuccess: () => {
    client.setQueryData(lifecycleKeys.workflow(promptId), createEvaluationWorkflow(promptId, true));
    void client.invalidateQueries({ queryKey: lifecycleKeys.prompts });
  } });
}
export function useWorkflowActionMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: submitWorkflowAction, onSuccess: (input) => {
    client.setQueryData<EvaluationWorkflow>(lifecycleKeys.workflow(promptId), (current) => applyWorkflowAction(current ?? createEvaluationWorkflow(promptId), input));
  } });
}
export function useReviewDecisionMutation() { const client = useQueryClient(); return useMutation({ mutationFn: decideReview, onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.reviews }) }); }
export function useSaveProviderMutation() { const client = useQueryClient(); return useMutation({ mutationFn: saveProvider, onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.providers }) }); }
export function useReleaseMutation() { const client = useQueryClient(); return useMutation({ mutationFn: releaseRevision, onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.prompts }) }); }

export function useRunPlaygroundMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { text: string; revisionIdA?: string; revisionIdB?: string }) => runPlaygroundComparison({ promptId, revisionIdA: input.revisionIdA ?? 'rev_prod', revisionIdB: input.revisionIdB ?? 'rev_draft', text: input.text }),
    onMutate: async (input) => {
      await client.cancelQueries({ queryKey: lifecycleKeys.playground(promptId) });
      const previous = client.getQueryData<PlaygroundRun[]>(lifecycleKeys.playground(promptId));
      const head = previous?.[0];
      if (head) {
        const optimistic: PlaygroundRun = {
          id: `optimistic_${Date.now().toString(36)}`,
          promptId: head.promptId,
          revisionId: input.revisionIdB ?? 'rev_draft',
          label: `Run ${new Date().toISOString().slice(11, 16)}`,
          input: input.text,
          outputA: head.outputB,
          outputB: head.outputA,
          tokensA: head.tokensB,
          tokensB: head.tokensA,
          costA: head.costB,
          costB: head.costA,
          scoreA: head.scoreB,
          scoreB: head.scoreA,
          createdAt: new Date().toISOString(),
        };
        client.setQueryData<PlaygroundRun[]>(lifecycleKeys.playground(promptId), [optimistic, ...previous]);
      }
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) client.setQueryData(lifecycleKeys.playground(promptId), context.previous);
    },
    onSuccess: (result) => {
      client.setQueryData<PlaygroundRun[]>(lifecycleKeys.playground(promptId), (current) => {
        if (!current) return [result];
        const next = current.filter((run) => run.id !== result.id);
        return [result, ...next];
      });
    },
  });
}

export function useRunPromptTestMutation() {
  return useMutation({ mutationFn: (input: PromptTestInput) => runPromptTest(input) });
}

export function useRunEvalMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => runEvalSuite({ promptId }),
    onMutate: async () => {
      await client.cancelQueries({ queryKey: lifecycleKeys.evalRunLatest(promptId) });
      const previous = client.getQueryData<EvalRun>(lifecycleKeys.evalRunLatest(promptId));
      if (previous) {
        const optimistic: EvalRun = {
          ...previous,
          id: `optimistic_${Date.now().toString(36)}`,
          createdAt: new Date().toISOString(),
        };
        client.setQueryData(lifecycleKeys.evalRunLatest(promptId), optimistic);
      }
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) client.setQueryData(lifecycleKeys.evalRunLatest(promptId), context.previous);
    },
    onSuccess: (result) => {
      client.setQueryData(lifecycleKeys.evalRunLatest(promptId), result.evalRun);
    },
  });
}

export function useRunEvaluationDatasetMutation(promptId: string, promptBody: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => runEvaluationDataset({ promptId, datasetId, promptBody }),
    onSuccess: (result: EvalDatasetResult) => {
      client.setQueryData<EvalWorkspace>(lifecycleKeys.evalWorkspace(promptId, promptBody), (current) => {
        if (!current) return current;
        return { ...current, datasets: current.datasets.map((dataset) => dataset.id === result.id ? result : dataset) };
      });
    },
  });
}

export function useCreateEvaluationDatasetWithAiMutation(promptId: string, promptBody: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => createEvaluationDatasetWithAi({ promptId, promptBody }),
    onSuccess: (result: EvalDatasetResult) => {
      client.setQueryData<EvalWorkspace>(lifecycleKeys.evalWorkspace(promptId, promptBody), (current) => {
        if (!current) return current;
        return { ...current, datasets: [result, ...current.datasets] };
      });
    },
  });
}

export function usePromoteMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { revisionId: string; environment: PromoteEnvironment }) => promoteRevision(input),
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts });
      const promptId = input.revisionId.split('_').slice(0, 1).join('_') || input.revisionId;
      void client.invalidateQueries({ queryKey: lifecycleKeys.productionStats(promptId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
    },
  });
}

export function useRollbackMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { promptId: string; revisionId: string }) => rollbackToRevision(input),
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(input.promptId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.productionStats(input.promptId) });
    },
  });
}

export const datasetsOptions = queryOptions({
  queryKey: lifecycleKeys.datasets,
  queryFn: getDatasets,
  staleTime: 60_000,
});

export const datasetOptions = (datasetId: string) => queryOptions({
  queryKey: lifecycleKeys.dataset(datasetId),
  queryFn: () => getDataset(datasetId),
  staleTime: 60_000,
});

export function useSaveDatasetMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: saveDataset,
    onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.datasets }),
  });
}

export function useDeleteDatasetMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteDataset,
    onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.datasets }),
  });
}

// ============ WIZARD QUERIES ============

export const wizardStepsOptions = queryOptions({
  queryKey: ['lifecycle', 'wizard', 'steps'] as const,
  queryFn: getWizardSteps,
  staleTime: Infinity,
});

export function useWizardSuggestionMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (answers: WizardAnswers) => generatePromptSuggestions(answers),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['lifecycle', 'wizard'] });
    },
  });
}

// ============ SDK KEYS QUERIES ============

export const sdkKeysOptions = (promptId: string) => queryOptions({
  queryKey: ['lifecycle', 'sdkKeys', promptId] as const,
  queryFn: () => getSDKKeys(promptId),
  staleTime: 60_000,
});

export function useGenerateSDKKeyMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { promptId: string; environment: 'development' | 'staging' | 'production' }) => generateSDKKey(input.promptId, input.environment),
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: ['lifecycle', 'sdkKeys', input.promptId] });
    },
  });
}

export function useRevokeSDKKeyMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { promptId: string; keyId: string }) => revokeSDKKey(input.keyId).then(() => input),
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: ['lifecycle', 'sdkKeys', input.promptId] });
    },
  });
}

// ============ CONNECTED PRODUCTS QUERIES ============

export const connectedProductsOptions = (promptId: string) => queryOptions({
  queryKey: ['lifecycle', 'connectedProducts', promptId] as const,
  queryFn: () => getConnectedProducts(promptId),
  staleTime: 60_000,
});

export const productionOverviewOptions = (promptId: string) => queryOptions({
  queryKey: ['lifecycle', 'productionOverview', promptId] as const,
  queryFn: () => getProductionOverview(promptId),
  staleTime: 60_000,
});

// ============ REQUEST TRACES QUERIES ============

export const requestTracesOptions = (callRecordId: string) => queryOptions({
  queryKey: ['lifecycle', 'traces', callRecordId] as const,
  queryFn: () => getAllTraces(callRecordId),
  staleTime: 30_000,
});

// ============ EVALUATION TRENDS QUERIES ============

export const evalTrendsOptions = (promptId: string, days: number = 30) => queryOptions({
  queryKey: ['lifecycle', 'evalTrends', promptId, days] as const,
  queryFn: () => getEvalTrends(promptId, days),
  staleTime: 60_000,
});

// ============ WORKSPACE STATS QUERIES ============

export const workspaceStatsOptions = queryOptions({
  queryKey: lifecycleKeys.workspaceStats,
  queryFn: fetchWorkspaceStats,
  staleTime: 60_000,
});

// ============ FOLDER QUERIES ============

export const foldersOptions = queryOptions({
  queryKey: lifecycleKeys.folders,
  queryFn: getFolders,
  staleTime: 60_000,
});

// Called with no filters this is the folder's whole list — the one the filter
// bar reads its owner and tag options off, and the one the table shows until a
// filter narrows it. Each distinct filter set is its own cache entry, and the
// previous rows stay on screen while the next set loads so typing in the search
// box does not blank the table between keystrokes.
export const folderPromptsOptions = (folderId: string, filters: PromptFilterQuery = {}) => {
  // Normalised so that "no filter" is one cache entry however it was spelled —
  // an empty search box must not fetch the list a second time under a key of
  // its own.
  const search = filters.search?.trim();
  const query: PromptFilterQuery = {
    ...(search ? { search } : {}),
    ...(filters.ownerId ? { ownerId: filters.ownerId } : {}),
    ...(filters.tag ? { tag: filters.tag } : {}),
    ...(filters.access ? { access: filters.access } : {}),
  };
  return queryOptions({
    queryKey: ['lifecycle', 'folderPrompts', folderId, query] as const,
    queryFn: () => getPromptsByFolder(folderId, query),
    staleTime: 60_000,
    placeholderData: (previous: Prompt[] | undefined) => previous,
  });
};

// ============ PROMPT SEARCH & INDEXING QUERIES (real backend) ============

export const promptSearchOptions = (query: string, type: 'quick' | 'ai') => queryOptions({
  queryKey: lifecycleKeys.search(query, type),
  queryFn: () => searchPrompts(query, type),
  staleTime: 30_000,
});

export const promptIndexOptions = (promptId: string) => queryOptions({
  queryKey: lifecycleKeys.promptIndex(promptId),
  queryFn: () => getPromptIndexStatus(promptId),
  staleTime: 15_000,
});

export const promptIndexJobOptions = (jobId: string) => queryOptions({
  queryKey: lifecycleKeys.indexJob(jobId),
  queryFn: () => getPromptIndexJob(jobId),
  refetchInterval: (query) =>
    query.state.data?.status === 'pending' || query.state.data?.status === 'running'
      ? 1_000
      : false,
});

export function useTriggerPromptIndexMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => triggerPromptIndex(promptId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.promptIndex(promptId) });
    },
  });
}

export function useDeletePromptIndexMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => deletePromptIndex(promptId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.promptIndex(promptId) });
      void client.invalidateQueries({ queryKey: ['lifecycle', 'search'] });
    },
  });
}

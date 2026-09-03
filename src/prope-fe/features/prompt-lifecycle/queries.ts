import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  decideReview,
  createFolder,
  deleteFolder,
  updateFolder,
  fetchWorkspaceStats,
  generatePromptSuggestions,
  getEditorSuggestions,
  getFolders,
  getPrompt,
  getPromptByModelName,
  getPrompts,
  getPromptsByFolder,
  getPromptDiff,
  getProviders,
  getReview,
  getReviews,
  getWizardSteps,
  promoteRevision,
  improvePromptWithAi,
  savePrompt,
  searchPrompts,
  getPromptIndexStatus,
  getPromptIndexJob,
  triggerPromptIndex,
  updateRevisionTags,
  updateRevisionInPlace,
  deletePromptIndex,
  streamSimilarPromptsForImport,
  importPrompt,
  resolvePromptSource,
  retirePrompt,
  type RevisionUpdateInput,
  type PromptFilterQuery,
} from '@/features/prompt-lifecycle/api';
import {
  createDraft,
  promoteDraft,
  renameDraft,
  updateDraft,
  type DraftUpdateValues,
  type PromoteDraftResult,
} from '@/features/prompt-lifecycle/draftApi';
import {
  addProviderModel,
  createPriceRow,
  createProviderConfig,
  deleteProviderConfig,
  getPriceRows,
  getProviderConfigs,
  getProviderModels,
  refreshProviderModels,
  rotateProviderCredential,
  updateProviderConfig,
  verifyProviderConfig,
} from '@/features/prompt-lifecycle/providerApi';
import {
  createRouterCombo,
  deleteRouterCombo,
  getRouterCombos,
  replaceRouterCombo,
} from '@/features/prompt-lifecycle/routerComboApi';
import {
  createDataset,
  cancelEvalRun,
  deleteDataset as deleteEvalDataset,
  draftDataset,
  suggestDatasets,
  analyzeEvalRuns,
  getDataset as getEvalDataset,
  getDatasetAttachments,
  getDatasets as getEvalLibrary,
  getEvalRun as getEvalRunDetail,
  getEvalRunCases,
  getEvalSuite,
  replaceDatasetAttachments,
  startRunsFromAttachments,
  updateDataset,
} from '@/features/prompt-lifecycle/evalApi';
import { isTerminal, type DatasetWriteInput } from '@/features/prompt-lifecycle/evalTypes';
import { getInbox } from '@/features/prompt-lifecycle/improvementApi';
import {
  getConversationGraph,
  getPromptCallRecords,
  getPromptConversations,
  getPromptEvalRuns,
  getPromptUsage,
  type CallRecordQuery,
} from '@/features/prompt-lifecycle/insightsApi';
import type { CallSource, UsageWindow } from '@/features/prompt-lifecycle/insightsTypes';
import { getCallObservability, getEvalCaseTrace } from '@/features/prompt-lifecycle/traceApi';
import { getLifecycleSummary } from '@/features/prompt-lifecycle/lifecycleSummaryApi';
import type { PromoteEnvironment, Prompt, PromptDetail, Revision, SimilarityStep, WizardAnswers } from '@/features/prompt-lifecycle/types';

export const lifecycleKeys = {
  prompts: ['lifecycle', 'prompts'] as const,
  prompt: (id: string) => ['lifecycle', 'prompt', id] as const,
  lifecycleSummary: (id: string, versionId: string) => ['lifecycle', 'summary', id, versionId] as const,
  reviews: ['lifecycle', 'reviews'] as const,
  review: (id: string) => ['lifecycle', 'review', id] as const,
  providers: ['lifecycle', 'providers'] as const,
  // The real `provider_access` configurations, kept apart from the mock
  // `providers` list above.
  providerConfigs: ['lifecycle', 'providerConfigs'] as const,
  providerModels: (id: string) => ['lifecycle', 'providerModels', id] as const,
  prices: ['lifecycle', 'prices'] as const,
  // Router combos (ADR-0069). One key for the whole list: the rungs come
  // back inline, so there is no per-combo read for anything to key on.
  routerCombos: ['lifecycle', 'routerCombos'] as const,
  // One prompt's call metadata, keyed by every filter that changes the answer.
  // The filters are part of the key because they are applied server-side: two
  // different filter sets are two different responses, not one response the
  // client narrows.
  promptCalls: (id: string, filters: string) => ['lifecycle', 'calls', 'prompt', id, filters] as const,
  promptUsage: (id: string, window: string, source: string) => ['lifecycle', 'usage', id, window, source] as const,
  promptConversations: (id: string, window: string, cursor: string) =>
    ['lifecycle', 'conversations', id, window, cursor] as const,
  conversationGraph: (id: string, conversationId: string) =>
    ['lifecycle', 'conversation', id, conversationId] as const,
  promptEvalRuns: (id: string, versionId: string) => ['lifecycle', 'evalRuns', id, versionId] as const,
  callObservability: (promptId: string, callId: string, includeRequest: boolean) =>
    ['lifecycle', 'observability', 'call', promptId, callId, includeRequest] as const,
  evalCaseTrace: (runId: string, caseResultId: string) =>
    ['lifecycle', 'observability', 'evaluation', runId, caseResultId] as const,
  // prompt-improvement (ADR-0068). The inbox is workspace-wide and takes no
  // parameter — the visibility filter is applied on the SERVER, per prompt, so
  // there is nothing here for a key to vary on and nothing for a client-side
  // filter to be built out of later.
  improvementInbox: ['lifecycle', 'improvement', 'inbox'] as const,
  promptFindings: (id: string) => ['lifecycle', 'improvement', 'prompt', id] as const,
  improvementSchedule: (workspaceId: string) =>
    ['lifecycle', 'improvement', 'schedule', workspaceId] as const,
  editorSuggestions: ['lifecycle', 'editorSuggestions'] as const,
  promptDiff: (id: string, revA: string, revB: string) => ['lifecycle', 'diff', id, revA, revB] as const,
  workspaceStats: ['lifecycle', 'workspaceStats'] as const,
  folders: ['lifecycle', 'folders'] as const,
  search: (query: string, type: 'quick' | 'ai') => ['lifecycle', 'search', type, query] as const,
  promptIndex: (promptId: string) => ['lifecycle', 'prompt-index', promptId] as const,
  indexJob: (jobId: string) => ['lifecycle', 'prompt-index-job', jobId] as const,
  // ---- release control -----------------------------------------------------
  // Keyed by revision, not by prompt: the review screen answers for one version,
  // and the rail lets a reader move between them without leaving the tab.
  releaseScreen: (promptId: string, versionId: string) =>
    ['lifecycle', 'release', 'screen', promptId, versionId] as const,
  releases: (promptId: string) => ['lifecycle', 'release', 'history', promptId] as const,
  // ---- evaluation -----------------------------------------------------------
  // The dataset library and its runs share one source: this is the tree's data
  // and the /app/datasets pages' data alike.
  evalLibrary: ['lifecycle', 'eval', 'library'] as const,
  evalAttachments: (promptId: string) => ['lifecycle', 'eval', 'attachments', promptId] as const,
  evalRunDetail: (runId: string) => ['lifecycle', 'eval', 'run', runId] as const,
  evalRunCases: (runId: string) => ['lifecycle', 'eval', 'run', runId, 'cases'] as const,
  evalSuite: (suiteId: string) => ['lifecycle', 'eval', 'suite', suiteId] as const,
  evalDataset: (datasetId: string) => ['lifecycle', 'eval', 'dataset', datasetId] as const,
};

export const promptsOptions = queryOptions({ queryKey: lifecycleKeys.prompts, queryFn: getPrompts, staleTime: 60_000 });
export const promptOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.prompt(id), queryFn: () => getPrompt(id), staleTime: 60_000 });
export const promptByModelNameOptions = (namespace: string, name: string) => queryOptions({
  queryKey: [...lifecycleKeys.prompts, 'model-name', namespace, name],
  queryFn: () => getPromptByModelName(namespace, name),
  staleTime: 60_000,
});
export const lifecycleSummaryOptions = (id: string, versionId: string) => queryOptions({
  queryKey: lifecycleKeys.lifecycleSummary(id, versionId),
  queryFn: () => getLifecycleSummary(id, versionId),
  staleTime: 0,
});

export function useAiPromptEditMutation() {
  return useMutation({ mutationFn: improvePromptWithAi });
}

export function useUpdateRevisionTagsMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ revisionId, tags }: { revisionId: string; tags: string[] }) =>
      updateRevisionTags({ promptId, revisionId, tags }),
    onMutate: async ({ revisionId, tags }) => {
      await client.cancelQueries({ queryKey: lifecycleKeys.prompt(promptId) });
      const previous = client.getQueryData<PromptDetail>(lifecycleKeys.prompt(promptId));
      client.setQueryData<PromptDetail>(lifecycleKeys.prompt(promptId), (current) => current ? {
        ...current,
        revisions: current.revisions.map((revision) => revision.id === revisionId ? { ...revision, tags } : revision),
      } : current);
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) client.setQueryData(lifecycleKeys.prompt(promptId), context.previous);
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
    },
  });
}
export const reviewsOptions = queryOptions({ queryKey: lifecycleKeys.reviews, queryFn: getReviews, staleTime: 60_000 });

// ---- Version drafts ---------------------------------------------------------
// Drafts are the editable layer under an immutable version (A-021 stays true:
// nothing ever rewrites a saved revision). Every write lands on the prompt
// detail cache because drafts ride on `PromptDetail.drafts`; promotion also
// moves the released pointer, so the wider list caches go stale with it.

export function useCreateDraftMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { source: Revision }) => createDraft({ promptId, source: input.source }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
    },
  });
}

export function useUpdateDraftMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { draftId: string; values: DraftUpdateValues }) => updateDraft({ promptId, draftId: input.draftId, values: input.values }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
    },
  });
}

/** The in-place save of a never-published Draft version: the PATCH overwrites
 * the version itself, so the prompt query must refetch to show the new body. */
export function useUpdateRevisionMutation(promptId: string, versionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: RevisionUpdateInput) => updateRevisionInPlace(promptId, versionId, input),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
    },
  });
}

export function useRenameDraftMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { draftId: string; name: string }) => renameDraft({ promptId, draftId: input.draftId, name: input.name }),
    // Optimistic, like the tag editor: a rename is visible the instant the
    // input commits, and a failed write quietly puts the old name back.
    onMutate: async ({ draftId, name }) => {
      await client.cancelQueries({ queryKey: lifecycleKeys.prompt(promptId) });
      const previous = client.getQueryData<PromptDetail>(lifecycleKeys.prompt(promptId));
      client.setQueryData<PromptDetail>(lifecycleKeys.prompt(promptId), (current) => current ? {
        ...current,
        drafts: current.drafts.map((draft) => draft.id === draftId ? { ...draft, name } : draft),
      } : current);
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) client.setQueryData(lifecycleKeys.prompt(promptId), context.previous);
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
    },
  });
}

export function usePromoteDraftMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { draftId: string; revisions: Revision[] }): Promise<PromoteDraftResult> =>
      promoteDraft({ promptId, draftId: input.draftId, revisions: input.revisions }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts });
      void client.invalidateQueries({ queryKey: ['lifecycle', 'folderPrompts'] });
    },
  });
}

// The inbox, as a shareable option rather than the page's inline useQuery — the
// dashboard's findings card reads the same key, so one fetch serves both.
export const improvementInboxOptions = queryOptions({
  queryKey: lifecycleKeys.improvementInbox,
  queryFn: getInbox,
  staleTime: 30_000,
});
export const reviewOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.review(id), queryFn: () => getReview(id), staleTime: 60_000 });
export const providersOptions = queryOptions({ queryKey: lifecycleKeys.providers, queryFn: getProviders, staleTime: 60_000 });
// ---- provider_access -------------------------------------------------------

export const providerConfigsOptions = queryOptions({
  queryKey: lifecycleKeys.providerConfigs,
  queryFn: getProviderConfigs,
  staleTime: 60_000,
});

export const providerModelsOptions = (providerId: string) => queryOptions({
  queryKey: lifecycleKeys.providerModels(providerId),
  queryFn: () => getProviderModels(providerId),
  staleTime: 60_000,
});

export const priceRowsOptions = queryOptions({
  queryKey: lifecycleKeys.prices,
  queryFn: getPriceRows,
  staleTime: 60_000,
});

// ---- router combos (ADR-0069) ----------------------------------------------

export const routerCombosOptions = queryOptions({
  queryKey: lifecycleKeys.routerCombos,
  queryFn: getRouterCombos,
  staleTime: 60_000,
});

/**
 * Every write here invalidates the list and **nothing else** — deliberately.
 *
 * A combo is a template. Editing one changes what the *next* revision will copy
 * and changes nothing already released, so no prompt, revision or release query
 * goes stale when it is saved. Invalidating them anyway would be harmless
 * refetching that quietly tells the next reader of this file that a combo edit
 * does reach a released prompt.
 */
function useRouterComboWriteMutation<TInput, TResult>(mutationFn: (input: TInput) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.routerCombos });
    },
  });
}

export function useCreateRouterComboMutation() {
  return useRouterComboWriteMutation(createRouterCombo);
}

export function useReplaceRouterComboMutation() {
  return useRouterComboWriteMutation(
    (input: { comboId: string } & Parameters<typeof replaceRouterCombo>[1]) =>
      replaceRouterCombo(input.comboId, input),
  );
}

export function useDeleteRouterComboMutation() {
  return useRouterComboWriteMutation(deleteRouterCombo);
}

/** Anything that touches a configuration invalidates the list it came from. */
function useProviderWriteMutation<TInput, TResult>(mutationFn: (input: TInput) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.providerConfigs });
    },
  });
}

export function useCreateProviderMutation() { return useProviderWriteMutation(createProviderConfig); }

export function useUpdateProviderMutation() { return useProviderWriteMutation(updateProviderConfig); }
export function useDeleteProviderMutation() { return useProviderWriteMutation(deleteProviderConfig); }
export function useRotateCredentialMutation() { return useProviderWriteMutation(rotateProviderCredential); }

/** Verifying re-discovers the catalogue, so both lists go stale at once. */
export function useVerifyProviderMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: verifyProviderConfig,
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.providerConfigs });
      void client.invalidateQueries({ queryKey: lifecycleKeys.providerModels(result.provider_config_id) });
    },
  });
}

export function useRefreshProviderModelsMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: refreshProviderModels,
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.providerModels(result.provider_config_id) });
    },
  });
}

export function useAddProviderModelMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: addProviderModel,
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.providerModels(input.providerId) });
    },
  });
}

export function useCreatePriceRowMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createPriceRow,
    onSuccess: () => { void client.invalidateQueries({ queryKey: lifecycleKeys.prices }); },
  });
}

export const editorSuggestionsOptions = (promptBody: string) => queryOptions({
  queryKey: [...lifecycleKeys.editorSuggestions, promptBody.length] as const,
  queryFn: () => getEditorSuggestions(promptBody),
  staleTime: 60_000,
});

// ---- prompt detail: Log, Production, Eval (step 6) --------------------------
//
// The three reads that replaced this module's fixtures. Short stale times: these
// answer "what is happening right now", and a reader who refreshes because the
// number looks wrong should get a new number.

export const promptCallRecordsOptions = (query: CallRecordQuery) => queryOptions({
  queryKey: lifecycleKeys.promptCalls(
    query.promptId,
    // Serialised rather than spread, so adding a filter cannot silently produce
    // a key that collides with an older shape still in the cache.
    JSON.stringify({
      cursor: query.cursor ?? null,
      source: query.source ?? null,
      outcome: query.outcome ?? null,
      versionId: query.versionId ?? null,
      window: query.window ?? null,
    }),
  ),
  queryFn: () => getPromptCallRecords(query),
  staleTime: 15_000,
});

export const promptConversationsOptions = (
  promptId: string,
  window: UsageWindow | null,
  cursor: string | null,
) => queryOptions({
  queryKey: lifecycleKeys.promptConversations(promptId, window ?? 'all', cursor ?? ''),
  queryFn: () => getPromptConversations(promptId, window, cursor),
  staleTime: 15_000,
});

/**
 * One conversation's graph. Longer stale time than the list: a conversation that
 * has finished does not change, and the ones a reader opens are almost always
 * finished. A live one is still refetched on mount, which is when it matters.
 */
export const conversationGraphOptions = (promptId: string, conversationId: string) => queryOptions({
  queryKey: lifecycleKeys.conversationGraph(promptId, conversationId),
  queryFn: () => getConversationGraph(promptId, conversationId),
  staleTime: 60_000,
});

export const promptUsageOptions = (promptId: string, window: UsageWindow, source: CallSource | null) => queryOptions({
  queryKey: lifecycleKeys.promptUsage(promptId, window, source ?? 'all'),
  queryFn: () => getPromptUsage(promptId, window, source),
  staleTime: 30_000,
});

/**
 * A prompt's runs, polled while any of them is still moving.
 *
 * The start endpoint answers 202 and the executor picks the run up out of band,
 * so somebody who starts a suite and walks straight to this tab arrives before
 * anything has been written. Without the interval the list they landed on was
 * the one fetched on mount and stayed that way — a run in flight looked like no
 * run at all, which is the same screen as "never evaluated".
 *
 * Same two seconds and the same terminal-status stop as `evalRunDetailOptions`,
 * so a run and the list it appears in agree about when it finished. `staleTime`
 * stays at 30 s for the settled case: a list of finished runs does not change on
 * its own, and the interval is `false` there anyway.
 */
export const promptEvalRunsOptions = (promptId: string, versionId?: string | null) => queryOptions({
  queryKey: lifecycleKeys.promptEvalRuns(promptId, versionId ?? 'all'),
  queryFn: () => getPromptEvalRuns(promptId, versionId),
  staleTime: 30_000,
  refetchInterval: (query) =>
    query.state.data?.some((run) => !isTerminal(run.status)) ? 2_000 : false,
});

export const callObservabilityOptions = (promptId: string, callId: string, includeRequest: boolean) => queryOptions({
  queryKey: lifecycleKeys.callObservability(promptId, callId, includeRequest),
  queryFn: () => getCallObservability(promptId, callId, includeRequest),
  staleTime: includeRequest ? 0 : 60_000,
  gcTime: includeRequest ? 0 : 5 * 60_000,
});

export const evalCaseTraceOptions = (runId: string, caseResultId: string) => queryOptions({
  queryKey: lifecycleKeys.evalCaseTrace(runId, caseResultId),
  queryFn: () => getEvalCaseTrace(runId, caseResultId),
  staleTime: 60_000,
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
  return useMutation({
    // Streaming rather than a single POST, and `onStep` travels in the variables
    // rather than in a closure so the mutation stays one call per press: the
    // rungs report as they finish and the bottom sheet renders them, and the
    // final frame is the same payload the JSON form returns.
    mutationFn: ({ text, onStep }: { text: string; onStep: (step: SimilarityStep) => void }) =>
      streamSimilarPromptsForImport(text, onStep, 5),
  });
}

/** The convert-or-wrap half of an import. Writes nothing, so it invalidates
 * nothing — its result goes into the form for somebody to read first. */
export function useResolvePromptSourceMutation() {
  return useMutation({ mutationFn: resolvePromptSource });
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

export function useRetirePromptMutation(folderId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: retirePrompt,
    onSuccess: (_result, promptId) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
      void client.invalidateQueries({ queryKey: ['lifecycle', 'folderPrompts', folderId] });
      void client.invalidateQueries({ queryKey: lifecycleKeys.folders });
    },
  });
}
export function useReviewDecisionMutation() { const client = useQueryClient(); return useMutation({ mutationFn: decideReview, onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.reviews }) }); }

export function usePromoteMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { revisionId: string; environment: PromoteEnvironment }) => promoteRevision(input),
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts });
      const promptId = input.revisionId.split('_').slice(0, 1).join('_') || input.revisionId;
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
    },
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

// ============ CONNECTED PRODUCTS QUERIES ============

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

// The three folder writes all invalidate the same two things: the grid, and the
// workspace stats above it. Only `create` can produce a folder the grid has
// never seen, but a rename changes a card's text and a delete removes one, and
// none of the three is frequent enough for a surgical cache patch to be worth
// the chance of it disagreeing with the server's union.
function useFolderWriteMutation<TInput, TResult>(mutationFn: (input: TInput) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.folders });
      void client.invalidateQueries({ queryKey: lifecycleKeys.workspaceStats });
    },
  });
}

export function useCreateFolderMutation() {
  return useFolderWriteMutation(createFolder);
}

export function useUpdateFolderMutation() {
  return useFolderWriteMutation(updateFolder);
}

export function useDeleteFolderMutation() {
  return useFolderWriteMutation(deleteFolder);
}

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

// ---- evaluation -------------------------------------------------------------
//
// These call `src/prope/evaluation` and nothing else.

export const evalLibraryOptions = queryOptions({
  queryKey: lifecycleKeys.evalLibrary,
  queryFn: getEvalLibrary,
  // The Chung catalogue ships in the image and cannot change under a running
  // container, so refetching it is work nobody asked for. Workspace-owned
  // writes invalidate this key explicitly.
  staleTime: 5 * 60_000,
});

export const evalAttachmentsOptions = (promptId: string) => queryOptions({
  queryKey: lifecycleKeys.evalAttachments(promptId),
  queryFn: () => getDatasetAttachments(promptId),
  staleTime: 30_000,
});

/**
 * Tick or untick — one mutation, because the endpoint takes the whole state.
 *
 * The response is the server's own view of the attachment list, so it is
 * written straight into the cache rather than invalidated: an optimistic tick
 * that then had to re-fetch would flicker the checkbox somebody just clicked.
 */
export function useReplaceDatasetAttachmentsMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (datasetIds: string[]) => replaceDatasetAttachments(promptId, datasetIds),
    onSuccess: (attachments) => {
      client.setQueryData(lifecycleKeys.evalAttachments(promptId), attachments);
    },
  });
}

/**
 * Materialise the attachments into suites and start the runs.
 *
 * Invalidates the attachment list on success because the run is what stamps
 * `suite_id` and clears `stale` — without this the tree would keep claiming a
 * set had never been run. The run lists are invalidated too: their polling
 * only stays alive while the rows they already hold are non-terminal, so a
 * list read before the start would never learn the run existed — the tab kept
 * claiming nothing was running, the results tiles froze on the previous batch,
 * and the advisor's fix proposal waited for a remount instead of the run.
 */
export function useStartEvalRunsMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) => startRunsFromAttachments(promptId, versionId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.evalAttachments(promptId) });
      void client.invalidateQueries({ queryKey: ['lifecycle', 'evalRuns'] });
      void client.invalidateQueries({ queryKey: ['floating-agent', 'events'] });
    },
  });
}

/**
 * Cancel one run: queued or running becomes interrupted.
 *
 * The invalidated keys are every view that polls a run's liveness — the run
 * row, its case list, the prompt's run history — plus the mascot's feed, whose
 * evaluation entries mirror the same run. A 409 (the run finished first) is
 * surfaced as an error, not swallowed: the screen showing a Cancel button for
 * a finished run is exactly the staleness worth reporting.
 */
export function useCancelEvalRunMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => cancelEvalRun(runId),
    onSuccess: (_data, runId) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.evalRunDetail(runId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.evalRunCases(runId) });
      void client.invalidateQueries({ queryKey: ['lifecycle', 'evalRuns'] });
      void client.invalidateQueries({ queryKey: ['floating-agent', 'events'] });
    },
  });
}

/**
 * One run, polled while it is still moving.
 *
 * Two seconds, and the interval stops at a terminal status rather than at a
 * timeout: the evaluation module's own success criterion is a suite completing
 * inside 120 s p95, and a poll that gave up earlier would leave the page
 * claiming "running" about a run that had finished.
 */
export const evalRunDetailOptions = (runId: string) => queryOptions({
  queryKey: lifecycleKeys.evalRunDetail(runId),
  queryFn: () => getEvalRunDetail(runId),
  refetchInterval: (query) => {
    const status = query.state.data?.status;
    return status && isTerminal(status) ? false : 2_000;
  },
});

/**
 * Per-case results, polled on the same clock as the run.
 *
 * Fetched *during* the run, not only after it: the executor writes a
 * `case_result` row as each case finishes, so the list fills in progressively
 * and a twenty-case suite stops being a spinner with nothing behind it.
 */
export const evalRunCasesOptions = (runId: string, live: boolean) => queryOptions({
  queryKey: lifecycleKeys.evalRunCases(runId),
  queryFn: () => getEvalRunCases(runId),
  refetchInterval: live ? 2_000 : false,
});

export const evalSuiteOptions = (suiteId: string) => queryOptions({
  queryKey: lifecycleKeys.evalSuite(suiteId),
  queryFn: () => getEvalSuite(suiteId),
  // A suite version is immutable by construction (A-004), so once read it can
  // never be out of date.
  staleTime: Infinity,
});

// ---- the writable dataset library ------------------------------------------

export const evalDatasetOptions = (datasetId: string) => queryOptions({
  queryKey: lifecycleKeys.evalDataset(datasetId),
  queryFn: () => getEvalDataset(datasetId),
  staleTime: 60_000,
});

/**
 * Every library write goes through here, because they all invalidate the same
 * two things: the tree, and the attachment list of whatever prompt is on screen.
 *
 * The attachment list matters even for an edit that touches no attachment — the
 * fingerprint moved, so `stale` flipped on every prompt that had ticked this
 * set, and the tree would otherwise keep saying "đã chạy" about a suite that no
 * longer matches. `promptId` is absent when the write came from the dataset
 * library pages, where no prompt is on screen and there is nothing to refresh
 * beyond the library itself.
 */
function useLibraryWriteMutation<TInput, TResult>(
  promptId: string | undefined,
  mutationFn: (input: TInput) => Promise<TResult>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.evalLibrary });
      if (promptId !== undefined) {
        void client.invalidateQueries({ queryKey: lifecycleKeys.evalAttachments(promptId) });
      }
    },
  });
}

export function useCreateEvalDatasetMutation(promptId?: string) {
  return useLibraryWriteMutation(promptId, createDataset);
}

export function useUpdateEvalDatasetMutation(promptId?: string) {
  const client = useQueryClient();
  const write = useLibraryWriteMutation(
    promptId,
    (input: { datasetId: string; body: DatasetWriteInput }) =>
      updateDataset(input.datasetId, input.body),
  );
  return {
    ...write,
    mutate: (
      input: { datasetId: string; body: DatasetWriteInput },
      options?: Parameters<typeof write.mutate>[1],
    ) => {
      // The edited dataset's own detail is cached by id and would otherwise
      // serve the pre-edit cases the next time the editor opened.
      void client.invalidateQueries({ queryKey: lifecycleKeys.evalDataset(input.datasetId) });
      write.mutate(input, options);
    },
  };
}

export function useDeleteEvalDatasetMutation(promptId?: string) {
  return useLibraryWriteMutation(promptId, deleteEvalDataset);
}

/**
 * Drafting is one model call over a whole prompt body, so it is slow by nature
 * and gets no retry: a second attempt costs a second call and the failure it
 * would be retrying is usually the agent being down, which a retry cannot fix.
 */
export function useDraftEvalDatasetMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: (input: { versionId?: string; folder?: string; caseTarget?: number; brief?: string }) =>
      draftDataset(promptId, input),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.evalLibrary });
    },
  });
}

/**
 * The advisor's two advice reads. Like drafting, they get no retry — a second
 * attempt re-reads everything for an answer the first call already gave or
 * refused. Neither writes anything: a suggestion is attached by ticking it,
 * and the brief is text.
 */
export function useSuggestEvalDatasetsMutation(promptId: string) {
  return useMutation({
    retry: false,
    mutationFn: (input: { versionId?: string }) => suggestDatasets(promptId, input),
  });
}

export function useAnalyzeEvalRunsMutation(promptId: string) {
  return useMutation({
    retry: false,
    mutationFn: (input: { versionId: string }) => analyzeEvalRuns(promptId, input),
  });
}

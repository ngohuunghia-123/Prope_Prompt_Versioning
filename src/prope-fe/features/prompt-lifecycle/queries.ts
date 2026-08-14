import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createPrompt,
  decideReview,
  deletePromptIndex,
  getCallRecords,
  getPrompt,
  getPrompts,
  getPromptIndexJob,
  getPromptIndexStatus,
  getProviders,
  getReleases,
  getReviewScreen,
  getReviews,
  releaseRevision,
  savePrompt,
  saveProvider,
  searchPrompts,
  startEvaluation,
  submitRevision,
  triggerPromptIndex,
  withdrawRelease,
} from '@/features/prompt-lifecycle/api';
import { getEvaluationWorkflow, startMockEvaluation, submitWorkflowAction } from '@/features/prompt-lifecycle/workflowMock';
import { createEvaluationWorkflow } from '@/features/prompt-lifecycle/workflowData';
import { applyWorkflowAction } from '@/features/prompt-lifecycle/workflowTransitions';
import type { EvaluationWorkflow, WorkflowAction } from '@/features/prompt-lifecycle/types';

/**
 * **Query keys carry the workspace.** Every read below is tenant-scoped on the
 * server — a session names exactly one workspace and the row-level policy filters
 * on it — so a cache keyed without it would serve one tenant's prompts to another
 * after a workspace switch, which is a cross-tenant leak the server never made.
 * Signing out clears the cache outright (`useLogoutMutation`); this is the belt
 * for everything short of that.
 */
export const lifecycleKeys = {
  prompts: (workspaceId: string) => ['lifecycle', workspaceId, 'prompts'] as const,
  prompt: (workspaceId: string, id: string) => ['lifecycle', workspaceId, 'prompt', id] as const,
  reviews: (workspaceId: string) => ['lifecycle', workspaceId, 'reviews'] as const,
  reviewScreen: (promptId: string, versionId: string) =>
    ['lifecycle', 'review-screen', promptId, versionId] as const,
  providers: ['lifecycle', 'providers'] as const,
  releases: (promptId: string) => ['lifecycle', 'releases', promptId] as const,
  calls: (promptId: string) => ['lifecycle', 'calls', promptId] as const,
  workflow: (id: string) => ['lifecycle', 'workflow', id] as const,
  search: (workspaceId: string, query: string, type: 'quick' | 'ai') =>
    ['lifecycle', workspaceId, 'search', type, query] as const,
  promptIndex: (workspaceId: string, promptId: string) =>
    ['lifecycle', workspaceId, 'prompt-index', promptId] as const,
  indexJob: (workspaceId: string, jobId: string) =>
    ['lifecycle', workspaceId, 'prompt-index-job', jobId] as const,
};

export const promptsOptions = (workspaceId: string) =>
  queryOptions({
    queryKey: lifecycleKeys.prompts(workspaceId),
    queryFn: () => getPrompts(workspaceId),
    staleTime: 60_000,
  });

export const promptSearchOptions = (
  workspaceId: string,
  query: string,
  type: 'quick' | 'ai',
) => queryOptions({
  queryKey: lifecycleKeys.search(workspaceId, query, type),
  queryFn: () => searchPrompts(query, type),
  staleTime: 30_000,
});

export const promptIndexOptions = (workspaceId: string, promptId: string) =>
  queryOptions({
    queryKey: lifecycleKeys.promptIndex(workspaceId, promptId),
    queryFn: () => getPromptIndexStatus(promptId),
    staleTime: 15_000,
  });

export const promptIndexJobOptions = (workspaceId: string, jobId: string) =>
  queryOptions({
    queryKey: lifecycleKeys.indexJob(workspaceId, jobId),
    queryFn: () => getPromptIndexJob(jobId),
    refetchInterval: (query) =>
      query.state.data?.status === 'pending' || query.state.data?.status === 'running'
        ? 1_000
        : false,
  });

export const promptOptions = (workspaceId: string, id: string) =>
  queryOptions({
    queryKey: lifecycleKeys.prompt(workspaceId, id),
    queryFn: () => getPrompt(id, workspaceId),
    staleTime: 60_000,
  });

export const reviewsOptions = (workspaceId: string) =>
  queryOptions({
    queryKey: lifecycleKeys.reviews(workspaceId),
    queryFn: () => getReviews(workspaceId),
    staleTime: 60_000,
  });

export const reviewScreenOptions = (promptId: string, versionId: string) =>
  queryOptions({
    queryKey: lifecycleKeys.reviewScreen(promptId, versionId),
    queryFn: () => getReviewScreen(promptId, versionId),
    // Short, because it carries the eval evidence a decision is made on and a run
    // can finish while the screen is open. A stale pass count on the screen
    // somebody approves from is the one number that must not be stale.
    staleTime: 10_000,
  });

export const providersOptions = queryOptions({
  queryKey: lifecycleKeys.providers,
  queryFn: getProviders,
  staleTime: 60_000,
});

export const releasesOptions = (promptId: string) =>
  queryOptions({
    queryKey: lifecycleKeys.releases(promptId),
    queryFn: () => getReleases(promptId),
    staleTime: 30_000,
  });

/**
 * ADR-0055. Per prompt, because there is no workspace-wide list and there must not
 * be one: every record names a prompt id, so a flat list would say that a private
 * prompt exists.
 */
export const callRecordsOptions = (promptId: string, promptTitle: string) =>
  queryOptions({
    queryKey: lifecycleKeys.calls(promptId),
    queryFn: () => getCallRecords(promptId, promptTitle),
    staleTime: 30_000,
  });

/** FIXTURE-BACKED. See `workflowMock.ts` — nothing here reaches a server. */
export const workflowOptions = (id: string) =>
  queryOptions({
    queryKey: lifecycleKeys.workflow(id),
    queryFn: () => getEvaluationWorkflow(id),
    staleTime: 60_000,
    refetchInterval: (query) => (query.state.data?.currentStepId === 'LoadContext' ? 800 : false),
  });

export function useSavePromptMutation(workspaceId: string, promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (values: Parameters<typeof savePrompt>[1]) => savePrompt(promptId, values),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts(workspaceId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(workspaceId, promptId) });
    },
  });
}

export function useCreatePromptMutation(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createPrompt,
    onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.prompts(workspaceId) }),
  });
}

export function useTriggerPromptIndexMutation(workspaceId: string, promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => triggerPromptIndex(promptId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.promptIndex(workspaceId, promptId) });
    },
  });
}

export function useDeletePromptIndexMutation(workspaceId: string, promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => deletePromptIndex(promptId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.promptIndex(workspaceId, promptId) });
      void client.invalidateQueries({ queryKey: ['lifecycle', workspaceId, 'search'] });
    },
  });
}

export function useSubmitRevisionMutation(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { promptId: string; versionId: string }) =>
      submitRevision(input.promptId, input.versionId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.reviews(workspaceId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts(workspaceId) });
    },
  });
}

/**
 * Start an eval run against a revision. **This one is real** —
 * `POST /prompts/{id}/eval-runs`.
 *
 * It also nudges the fixture-backed stepper so the screen animates, which is the
 * seam between the real lifecycle and the invented one. When the stepper is
 * rebuilt on the real lifecycle (see `workflowMock.ts`), the second call goes and
 * this becomes an ordinary mutation.
 */
export function useStartEvaluationMutation(workspaceId: string, promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (versionId: string) => {
      const started = await startEvaluation(promptId, versionId);
      await startMockEvaluation();
      return started;
    },
    onSuccess: () => {
      client.setQueryData(lifecycleKeys.workflow(promptId), createEvaluationWorkflow(promptId, true));
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts(workspaceId) });
    },
  });
}

/** FIXTURE-BACKED. Records nothing and approves nothing. See `workflowMock.ts`. */
export function useWorkflowActionMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: submitWorkflowAction,
    onSuccess: (input: WorkflowAction) => {
      client.setQueryData<EvaluationWorkflow>(lifecycleKeys.workflow(promptId), (current) =>
        applyWorkflowAction(current ?? createEvaluationWorkflow(promptId), input),
      );
    },
  });
}

export function useReviewDecisionMutation(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: decideReview,
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.reviews(workspaceId) });
      void client.invalidateQueries({
        queryKey: lifecycleKeys.reviewScreen(input.promptId, input.versionId),
      });
    },
  });
}

export function useSaveProviderMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: saveProvider,
    onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.providers }),
  });
}

export function useReleaseMutation(workspaceId: string, promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      values: Parameters<typeof releaseRevision>[1];
      expectedCurrent?: string | null;
    }) => releaseRevision(promptId, input.values, input.expectedCurrent),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts(workspaceId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(workspaceId, promptId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.releases(promptId) });
    },
  });
}

export function useWithdrawReleaseMutation(workspaceId: string, promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) => withdrawRelease(promptId, reason),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompts(workspaceId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(workspaceId, promptId) });
      void client.invalidateQueries({ queryKey: lifecycleKeys.releases(promptId) });
    },
  });
}

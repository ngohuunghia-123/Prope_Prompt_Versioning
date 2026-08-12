import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { decideReview, getCallRecords, getEvaluationWorkflow, getPrompt, getPrompts, getProviders, getReview, getReviews, releaseRevision, savePrompt, saveProvider, startEvaluation, submitWorkflowAction } from '@/features/prompt-lifecycle/api';
import { createEvaluationWorkflow } from '@/features/prompt-lifecycle/workflowData';
import { applyWorkflowAction } from '@/features/prompt-lifecycle/workflowTransitions';
import type { EvaluationWorkflow } from '@/features/prompt-lifecycle/types';

export const lifecycleKeys = {
  prompts: ['lifecycle', 'prompts'] as const,
  prompt: (id: string) => ['lifecycle', 'prompt', id] as const,
  reviews: ['lifecycle', 'reviews'] as const,
  review: (id: string) => ['lifecycle', 'review', id] as const,
  providers: ['lifecycle', 'providers'] as const,
  calls: ['lifecycle', 'calls'] as const,
  workflow: (id: string) => ['lifecycle', 'workflow', id] as const,
};

export const promptsOptions = queryOptions({ queryKey: lifecycleKeys.prompts, queryFn: getPrompts, staleTime: 60_000 });
export const promptOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.prompt(id), queryFn: () => getPrompt(id), staleTime: 60_000 });
export const reviewsOptions = queryOptions({ queryKey: lifecycleKeys.reviews, queryFn: getReviews, staleTime: 60_000 });
export const reviewOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.review(id), queryFn: () => getReview(id), staleTime: 60_000 });
export const providersOptions = queryOptions({ queryKey: lifecycleKeys.providers, queryFn: getProviders, staleTime: 60_000 });
export const callRecordsOptions = queryOptions({ queryKey: lifecycleKeys.calls, queryFn: getCallRecords, staleTime: 30_000 });
export const workflowOptions = (id: string) => queryOptions({ queryKey: lifecycleKeys.workflow(id), queryFn: () => getEvaluationWorkflow(id), staleTime: 60_000, refetchInterval: (query) => query.state.data?.currentStepId === 'LoadContext' ? 800 : false });

export function useSavePromptMutation() { const client = useQueryClient(); return useMutation({ mutationFn: savePrompt, onSuccess: () => client.invalidateQueries({ queryKey: lifecycleKeys.prompts }) }); }
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

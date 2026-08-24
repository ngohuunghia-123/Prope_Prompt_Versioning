import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { createCommitProposal, createImportBatch, decideCommitProposal, getImportBatch, getImportItems, updateImportItem } from '@/features/prompt-ingestion/api';

export const ingestionKeys = {
  batch: (id: string) => ['prompt-ingestion', 'batch', id] as const,
  items: (id: string) => ['prompt-ingestion', 'items', id] as const,
};
export const importBatchOptions = (id: string) => queryOptions({ queryKey: ingestionKeys.batch(id), queryFn: () => getImportBatch(id), refetchInterval: (query) => query.state.data?.status === 'processing' ? 1_500 : false });
export const importItemsOptions = (id: string) => queryOptions({ queryKey: ingestionKeys.items(id), queryFn: () => getImportItems(id), refetchInterval: (query) => query.state.data?.items.some((item) => ['parsed', 'converting', 'duplicate_check', 'retryable'].includes(item.state)) ? 1_500 : false });

export function useCreateImportBatch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createImportBatch,
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['floating-agent', 'events'] }); },
  });
}
export function useUpdateImportItem(batchId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, expectedVersion, resolution, targetPromptId }: { itemId: string; expectedVersion: number; resolution: 'create' | 'revise' | 'skip'; targetPromptId?: string | null }) => updateImportItem(batchId, itemId, { expected_version: expectedVersion, resolution, target_prompt_id: targetPromptId }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ingestionKeys.items(batchId) }); void client.invalidateQueries({ queryKey: ingestionKeys.batch(batchId) }); },
  });
}
export function useCreateCommitProposal(batchId: string) {
  return useMutation({ mutationFn: ({ reviewVersion, itemIds }: { reviewVersion: number; itemIds: string[] }) => createCommitProposal(batchId, reviewVersion, itemIds) });
}
export function useDecideCommitProposal(batchId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ proposalId, approve }: { proposalId: string; approve: boolean }) => decideCommitProposal(proposalId, approve),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ingestionKeys.batch(batchId) }); void client.invalidateQueries({ queryKey: ingestionKeys.items(batchId) }); },
  });
}

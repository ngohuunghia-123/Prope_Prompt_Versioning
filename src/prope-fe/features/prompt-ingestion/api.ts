import { apiRequest } from '@/lib/apiClient';
import { commitProposalSchema, commitResultSchema, importBatchSchema, importItemListSchema, importItemSchema } from '@/features/prompt-ingestion/types';

export const getImportBatch = (batchId: string) => apiRequest(`/api/v1/import-batches/${batchId}`, { schema: importBatchSchema });
export const getImportItems = (batchId: string) => apiRequest(`/api/v1/import-batches/${batchId}/items?limit=100`, { schema: importItemListSchema });

export function updateImportItem(batchId: string, itemId: string, payload: { expected_version: number; resolution: 'create' | 'revise' | 'skip'; target_prompt_id?: string | null }) {
  return apiRequest(`/api/v1/import-batches/${batchId}/items/${itemId}`, { method: 'PATCH', body: JSON.stringify(payload), schema: importItemSchema });
}

export function createCommitProposal(batchId: string, reviewVersion: number, itemIds: string[]) {
  return apiRequest(`/api/v1/import-batches/${batchId}/commit-proposals`, { method: 'POST', body: JSON.stringify({ expected_review_version: reviewVersion, item_ids: itemIds }), schema: commitProposalSchema });
}

export function decideCommitProposal(proposalId: string, approve: boolean) {
  return apiRequest(`/api/v1/action-proposals/${proposalId}/decision`, { method: 'POST', body: JSON.stringify({ approve }), schema: commitResultSchema });
}

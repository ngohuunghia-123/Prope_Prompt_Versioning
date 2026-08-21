import { apiRequest } from '@/lib/apiClient';
import { commitProposalSchema, commitResultSchema, importBatchSchema, importItemListSchema, importItemSchema, type UploadFormValues } from '@/features/prompt-ingestion/types';

export function createImportBatch(values: UploadFormValues) {
  const body = new FormData();
  for (const file of Array.from(values.files)) body.append('files', file);
  body.append('mode', values.mode);
  body.append('namespace', values.namespace);
  body.append('access_level', values.accessLevel);
  body.append('field_mapping', '{}');
  return apiRequest('/api/v1/import-batches', { method: 'POST', body, schema: importBatchSchema });
}

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

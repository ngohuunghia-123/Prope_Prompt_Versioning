import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import { labelingRecordSchema, type CallLabel, type LabelingRecord } from '@/features/labeling/types';

export function getLabelingQueue(): Promise<LabelingRecord[]> {
  return apiRequest('/api/v1/annotations?limit=50', { schema: z.array(labelingRecordSchema) });
}

export function saveCallLabel(promptId: string, callId: string, label: CallLabel): Promise<LabelingRecord> {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/call-records/${encodeURIComponent(callId)}/annotation`, {
    method: 'PUT',
    body: JSON.stringify(label),
    schema: labelingRecordSchema,
  });
}

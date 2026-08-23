import { z } from 'zod';

export const labelVerdictSchema = z.enum(['good', 'issue', 'review']);
export const callLabelSchema = z.object({ verdict: labelVerdictSchema, categories: z.array(z.string()), correction: z.string(), note: z.string() });
export const labelingRecordSchema = z.object({
  call_id: z.string(),
  prompt_id: z.string(),
  prompt_title: z.string(),
  revision_number: z.number().int().nullable(),
  consumer_label: z.string().nullable(),
  outcome: z.string(),
  created_at: z.string(),
  label: callLabelSchema.nullable(),
}).transform((record) => ({
  callId: record.call_id,
  promptId: record.prompt_id,
  promptTitle: record.prompt_title,
  revisionNumber: record.revision_number,
  consumerLabel: record.consumer_label,
  outcome: record.outcome,
  createdAt: record.created_at,
  label: record.label,
}));
export type CallLabel = z.infer<typeof callLabelSchema>;
export type LabelingRecord = z.infer<typeof labelingRecordSchema>;

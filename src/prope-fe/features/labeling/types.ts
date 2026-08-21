import { z } from 'zod';

export const labelVerdictSchema = z.enum(['good', 'issue', 'review']);
export const callLabelSchema = z.object({ verdict: labelVerdictSchema, categories: z.array(z.string()), correction: z.string(), note: z.string() });
export const labelingRecordSchema = z.object({ callId: z.string(), promptId: z.string(), promptTitle: z.string(), revision: z.string(), app: z.string(), outcome: z.string(), createdAt: z.string(), requestBody: z.string(), responseBody: z.string(), label: callLabelSchema.nullable() });
export type CallLabel = z.infer<typeof callLabelSchema>;
export type LabelingRecord = z.infer<typeof labelingRecordSchema>;

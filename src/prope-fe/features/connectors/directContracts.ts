import { z } from 'zod';
import { sourceSchema } from '@/features/connectors/contracts';

export const PANEL_OWNER = 'panel-user';
export const objectId = z.string().min(1).max(200).regex(/^[a-zA-Z0-9_:@.-]+$/);
export const directCaptureSchema = sourceSchema.omit({ host: true }).extend({ namespace: objectId }).strict();
export const revisionTargetSchema = z.object({ prompt_id: objectId, version_id: objectId }).strict();
export const attachmentWriteSchema = z.object({ prompt_id: objectId, dataset_ids: z.array(objectId).max(8) }).strict();
export const datasetWriteSchema = z.object({
  name: z.string().min(1).max(100), description: z.string().max(2000),
  kind: z.enum(['golden', 'regression', 'red-team']), tags: z.array(z.string().min(1).max(32)).max(10),
  output_modality: z.enum(['text', 'structured']), folder: z.string().max(63),
  cases: z.array(z.object({
    name: z.string().min(1).max(200),
    input_messages: z.array(z.object({ role: z.string().max(30), content: z.string().max(32768) }).strict()).min(1).max(100),
    input_variables: z.record(z.string(), z.string()),
    assertions: z.array(z.object({ type: z.string().max(100), value: z.unknown() }).strict()).max(100),
  }).strict()).min(1).max(100), copy_from: z.string().optional(),
}).strict();
export const improvementTargetSchema = revisionTargetSchema.extend({ eval_run_id: objectId }).strict();
export const improvementReviewSchema = revisionTargetSchema.extend({ run_id: objectId }).strict();
export const directRevisionSchema = revisionTargetSchema.extend({ source: z.string().min(1).max(32768), format: z.enum(['txt', 'markdown', 'xml']) }).strict();

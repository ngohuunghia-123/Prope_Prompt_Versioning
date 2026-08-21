import { z } from 'zod';

export const importBatchSchema = z.object({
  id: z.string(), mode: z.enum(['files', 'table']), status: z.string(),
  default_namespace: z.string(), default_access_level: z.enum(['private', 'workspace']),
  field_mapping: z.record(z.string(), z.string()), review_version: z.number(),
  item_count: z.number(), ready_count: z.number(), committed_count: z.number(), error_count: z.number(),
  created_at: z.string(), updated_at: z.string(), completed_at: z.string().nullable(), expires_at: z.string(),
});

const semanticMatchSchema = z.object({
  prompt_id: z.string(), title: z.string(), purpose: z.string(), similarity: z.number().nullable(),
});

export const importItemSchema = z.object({
  id: z.string(), batch_id: z.string(), ordinal: z.number(), source_filename: z.string(), source_format: z.string(),
  source_hash: z.string(), source_text: z.string(), title: z.string(), purpose: z.string(), namespace: z.string(),
  name: z.string(), tags: z.array(z.string()), change_summary: z.string(), canonical_body: z.string().nullable(),
  conversion_model: z.string().nullable(), conversion_schema_version: z.string().nullable(),
  semantic_matches: z.array(semanticMatchSchema), resolution: z.enum(['create', 'revise', 'skip']).nullable(),
  target_prompt_id: z.string().nullable(), base_version_id: z.string().nullable(), state: z.string(), error_code: z.string().nullable(),
  attempts: z.number(), item_version: z.number(), result_prompt_id: z.string().nullable(), result_version_id: z.string().nullable(),
  created_at: z.string(), updated_at: z.string(),
});

export const importItemListSchema = z.object({ items: z.array(importItemSchema), next_cursor: z.number().nullable() });
export const commitProposalSchema = z.object({ id: z.string(), batch_id: z.string(), status: z.string(), expected_review_version: z.number(), preview: z.record(z.string(), z.unknown()) });
export const commitResultSchema = z.object({ id: z.string(), status: z.string(), batch_id: z.string(), committed_count: z.number(), conflict_count: z.number() });

export type ImportBatch = z.infer<typeof importBatchSchema>;
export type ImportItem = z.infer<typeof importItemSchema>;

export const uploadFormSchema = z.object({
  namespace: z.string().trim().min(1).max(63).regex(/^[a-z0-9][a-z0-9._-]*$/),
  mode: z.enum(['files', 'table']), accessLevel: z.enum(['private', 'workspace']),
  files: z.custom<FileList>((value) => value instanceof FileList && value.length > 0),
});
export type UploadFormValues = z.infer<typeof uploadFormSchema>;

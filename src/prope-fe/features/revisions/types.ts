import { z } from 'zod';

export const revisionSchema = z.object({
  id: z.string().min(1),
  promptId: z.string().min(1),
  number: z.number().int().positive(),
  content: z.string().min(1),
  providerName: z.string().min(1),
  upstreamModel: z.string().min(1),
  temperature: z.number().min(0).max(2),
  maxTokens: z.number().int().positive(),
  fallbackAnswer: z.string(),
  summary: z.string().min(1),
  editorName: z.string().min(1),
  createdAt: z.string(),
  isCurrent: z.boolean(),
  status: z.enum(['draft', 'inReview', 'approved']),
});

export const revisionWorkspaceSchema = z.object({
  permission: z.enum(['edit', 'denied']),
  revisions: z.array(revisionSchema),
});

export const revisionFormSchema = z.object({
  content: z.string().trim().min(20, 'content'),
  providerName: z.string().trim().min(1, 'providerName'),
  upstreamModel: z.string().trim().min(1, 'upstreamModel'),
  temperature: z.number().min(0).max(2),
  maxTokens: z.number().int().positive(),
  fallbackAnswer: z.string().trim(),
  summary: z.string().trim().min(3, 'summary'),
});

export type PromptRevision = z.infer<typeof revisionSchema>;
export type RevisionFormValues = z.infer<typeof revisionFormSchema>;
export type RevisionWorkspace = z.infer<typeof revisionWorkspaceSchema>;

import { z } from 'zod';

export const promptStatusSchema = z.enum(['draft', 'inReview', 'approved']);
export const promptSourceSchema = z.literal('manual');
export const promptAccessSchema = z.enum(['private', 'team', 'organization']);

export const preservedPromptSchema = z.object({
  id: z.string(),
  title: z.string(),
  content: z.string(),
  purpose: z.string(),
  tags: z.array(z.string()),
  status: promptStatusSchema,
  source: promptSourceSchema,
  modelName: z.string(),
  providerName: z.string(),
  upstreamModel: z.string(),
  temperature: z.number().min(0).max(2),
  maxTokens: z.number().int().positive(),
  fallbackAnswer: z.string(),
  ownerId: z.string(),
  ownerName: z.string(),
  access: promptAccessSchema,
  createdAt: z.string(),
  updatedAt: z.string(),
  reuseCount: z.number().int().nonnegative(),
  currentRevision: z.number().int().positive(),
  currentVersionId: z.string().min(1),
  trustedRevision: z.number().int().positive().nullable(),
  trustedVersionId: z.string().nullable(),
  releasedRevision: z.number().int().positive().nullable(),
  releasedVersionId: z.string().nullable(),
});

export const promptListSchema = z.array(preservedPromptSchema);

export const promptFormSchema = z.object({
  source: promptSourceSchema,
  title: z.string().trim().min(3, 'title'),
  purpose: z.string().trim().min(10, 'purpose'),
  content: z.string().trim().min(20, 'content'),
  tags: z.string(),
  modelName: z.string().trim().regex(/^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9-]*$/, 'modelName'),
  providerName: z.string().min(1, 'provider'),
  upstreamModel: z.string().min(1, 'upstreamModel'),
  temperature: z.number().min(0, 'temperature').max(2, 'temperature'),
  maxTokens: z.number().int().positive('maxTokens'),
  fallbackAnswer: z.string().trim(),
  ownerId: z.string().min(1, 'owner'),
  ownerName: z.string().min(1),
  access: promptAccessSchema,
});

export type PreservedPrompt = z.infer<typeof preservedPromptSchema>;
export type PromptFormValues = z.infer<typeof promptFormSchema>;

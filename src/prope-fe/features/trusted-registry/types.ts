import { z } from 'zod';

export const registryStatusSchema = z.enum(['draft', 'inReview', 'approved', 'inUse', 'retired']);
export const registryAccessSchema = z.enum(['private', 'team', 'organization']);
export const revisionTrustSchema = z.enum(['trusted', 'untrusted']);

export const registryPromptSchema = z.object({
  id: z.string(),
  title: z.string(),
  purpose: z.string(),
  content: z.string(),
  tags: z.array(z.string()),
  ownerName: z.string(),
  modelName: z.string(),
  status: registryStatusSchema,
  accessLevel: registryAccessSchema,
  revisionTrust: revisionTrustSchema,
  currentRevision: z.number().int().positive(),
  trustedRevision: z.number().int().positive().nullable(),
  trustedVersionId: z.string().nullable(),
  updatedAt: z.string(),
});

export const registryPromptListSchema = z.array(registryPromptSchema);

export type RegistryPrompt = z.infer<typeof registryPromptSchema>;

import { z } from 'zod';

export const reviewDecisionFormSchema = z.object({
  decision: z.enum(['approved', 'changesRequested']),
  reason: z.string().trim().min(3, 'reason'),
  comment: z.string().trim(),
  diffReviewed: z.boolean().refine(Boolean, 'checklist'),
  evidenceReviewed: z.boolean().refine(Boolean, 'checklist'),
  usageReviewed: z.boolean().refine(Boolean, 'checklist'),
});

export const reviewTaskSchema = z.object({
  id: z.string().min(1), promptId: z.string().min(1), promptTitle: z.string().min(1), ownerName: z.string().min(1),
  revisionNumber: z.number().int().positive(), versionId: z.string().min(1), createdAt: z.string(), dueAt: z.string().nullable(),
  kind: z.enum(['revisionReview', 'breakGlassFollowUp']),
});

export const reviewTaskListSchema = z.array(reviewTaskSchema);

export const reviewWorkspaceSchema = z.object({
  promptId: z.string().min(1),
  promptTitle: z.string().min(1),
  permission: z.enum(['review', 'denied']),
  revisionId: z.string().min(1),
  revisionNumber: z.number().int().positive(),
  changeSummary: z.string().min(1),
  authorName: z.string().min(1),
  submittedAt: z.string(),
  beforeContent: z.string().min(1),
  candidateContent: z.string().min(1),
  modelName: z.string().min(1),
  usageContext: z.string().min(1),
  fallbackAnswer: z.string(),
  suites: z.array(z.object({ name: z.string().min(1), version: z.number().int().positive(), modality: z.enum(['text', 'structured']), passed: z.number().int().nonnegative(), failed: z.number().int().nonnegative(), errored: z.number().int().nonnegative(), costDelta: z.number().nullable() })),
  requiresAcknowledgement: z.boolean(),
  decision: z.object({ status: z.enum(['approved', 'changesRequested']), reason: z.string(), comment: z.string(), reviewerName: z.string(), decidedAt: z.string() }).nullable(),
});

export type ReviewDecisionFormValues = z.infer<typeof reviewDecisionFormSchema>;
export type ReviewWorkspace = z.infer<typeof reviewWorkspaceSchema>;
export type ReviewTask = z.infer<typeof reviewTaskSchema>;

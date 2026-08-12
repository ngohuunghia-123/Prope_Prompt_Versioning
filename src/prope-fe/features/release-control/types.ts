import { z } from 'zod';

export const releaseRecordSchema = z.object({
  id: z.string().min(1), revisionId: z.string().min(1), revisionNumber: z.number().int().positive(), versionId: z.string().min(1),
  releasedBy: z.string().min(1), releasedAt: z.string(), reason: z.string().min(3), current: z.boolean(), kind: z.enum(['release', 'restore', 'breakGlass']), approvalId: z.string().nullable(),
});

export const releaseWorkspaceSchema = z.object({
  promptId: z.string().min(1), permission: z.enum(['release', 'denied']),
  candidateRevisionId: z.string().min(1), candidateRevisionNumber: z.number().int().positive(),
  modelName: z.string().min(1), usageContext: z.string().min(1),
  approverName: z.string().min(1), approvedAt: z.string(), approvalReason: z.string().min(1),
  releases: z.array(releaseRecordSchema),
});

export const releaseDecisionFormSchema = z.object({ reason: z.string().trim().min(3, 'reason'), breakGlass: z.boolean() });
export const restoreDecisionFormSchema = z.object({ revisionId: z.string().min(1, 'revision'), reason: z.string().trim().min(3, 'reason') });

export type ReleaseWorkspace = z.infer<typeof releaseWorkspaceSchema>;
export type ReleaseDecisionFormValues = z.infer<typeof releaseDecisionFormSchema>;
export type RestoreDecisionFormValues = z.infer<typeof restoreDecisionFormSchema>;

export function getRestoreCandidates(workspace: ReleaseWorkspace) {
  return workspace.releases.filter((record, index, records) => !record.current && record.approvalId !== null && records.findIndex((other) => other.revisionId === record.revisionId && !other.current && other.approvalId !== null) === index);
}

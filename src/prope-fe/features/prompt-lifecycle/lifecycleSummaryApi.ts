import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';

export const lifecycleSummarySchema = z.object({
  prompt_id: z.string(), version_id: z.string(),
  phase: z.enum(['draft', 'evaluated', 'waiting_review', 'approved', 'live', 'attention']),
  live_version_id: z.string().nullable().default(null),
  last_eval: z.object({
    run_id: z.string(), status: z.string(), passed: z.number().int().nonnegative(),
    failed: z.number().int().nonnegative(), errors: z.number().int().nonnegative(),
    total: z.number().int().nonnegative(), finished_at: z.string().nullable().default(null),
  }).nullable().default(null),
  approval_status: z.string(), open_finding_count: z.number().int().nonnegative(),
  readiness_attention_count: z.number().int().nonnegative().nullable().default(null),
  next_action: z.enum(['run_evaluation', 'edit_prompt', 'submit_review', 'view_release', 'release', 'view_activity', 'view_improvements']),
});

export type LifecycleSummary = z.infer<typeof lifecycleSummarySchema>;

export function getLifecycleSummary(promptId: string, versionId: string) {
  return apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/lifecycle-summary?version_id=${encodeURIComponent(versionId)}`, { schema: lifecycleSummarySchema });
}

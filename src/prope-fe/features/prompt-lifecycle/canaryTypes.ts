import { z } from 'zod';

export const canarySchema = z.object({
  promptId: z.string(), baselineVersionId: z.string(), candidateVersionId: z.string(), percentage: z.number().int().min(5).max(50),
  status: z.enum(['active', 'stopped', 'promoted']), startedBy: z.string(), startedAt: z.string(), revision: z.number().int().nonnegative(),
});
export type Canary = z.infer<typeof canarySchema>;

export const canaryMetricSchema = z.object({ versionId: z.string(), requests: z.number(), errorRate: z.number(), fallbackRate: z.number(), latencyMs: z.number(), tokens: z.number(), cost: z.number() });
export type CanaryMetric = z.infer<typeof canaryMetricSchema>;

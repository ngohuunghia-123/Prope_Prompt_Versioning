import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { canarySchema, type Canary, type CanaryMetric } from '@/features/prompt-lifecycle/canaryTypes';

const key = (promptId: string) => ['lifecycle', 'canary', promptId] as const;
const storageKey = (promptId: string) => `prope-canary-${promptId}`;
const read = (promptId: string): Canary | null => {
  const value = localStorage.getItem(storageKey(promptId));
  if (!value) return null;
  try {
    const parsed = canarySchema.safeParse(JSON.parse(value));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
};
const write = (canary: Canary | null) => {
  if (canary) localStorage.setItem(storageKey(canary.promptId), JSON.stringify(canary));
  else return;
};

export const canaryOptions = (promptId: string) => queryOptions({ queryKey: key(promptId), queryFn: async () => read(promptId) });
export const canaryMetricsOptions = (canary: Canary | null) => queryOptions({
  queryKey: ['lifecycle', 'canary', canary?.promptId ?? '', 'metrics', canary?.revision ?? 0],
  enabled: Boolean(canary && canary.status === 'active'),
  queryFn: async (): Promise<CanaryMetric[]> => canary ? [
    { versionId: canary.baselineVersionId, requests: 920, errorRate: 0.024, fallbackRate: 0.008, latencyMs: 842, tokens: 184200, cost: 4.82 },
    { versionId: canary.candidateVersionId, requests: 80, errorRate: 0.018, fallbackRate: 0.006, latencyMs: 801, tokens: 15120, cost: 0.39 },
  ] : [],
});

export function useCanaryMutation(promptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (next: Canary | null) => { if (next) write(next); else localStorage.removeItem(storageKey(promptId)); return next; },
    onSuccess: (next) => client.setQueryData(key(promptId), next),
  });
}

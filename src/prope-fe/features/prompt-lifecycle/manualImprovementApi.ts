import { z } from 'zod';

import { agentRunSchema, type AgentRun } from '@/features/floating-agent/types';
import { apiRequest } from '@/lib/apiClient';

export function listManualImprovementRuns(promptId: string): Promise<AgentRun[]> {
  const params = new URLSearchParams({ kind: 'improvement', prompt_id: promptId, limit: '5' });
  return apiRequest(`/api/v1/agent-runs?${params.toString()}`, { schema: z.array(agentRunSchema) });
}

export function startManualImprovement(
  promptId: string,
  versionId: string,
  evidenceSource: 'production' | 'eval_analysis' = 'production',
): Promise<AgentRun> {
  return apiRequest('/api/v1/agent-runs', {
    method: 'POST',
    body: JSON.stringify({
      kind: 'improvement', plan_basis: 'explicit_user_action',
      prompt_id: promptId, version_id: versionId,
      // ADR-0070: `eval_analysis` runs the advisor→draft→rails→gate pipeline
      // over the eval runs; `production` is the daily drift sweep, on demand.
      evidence_source: evidenceSource,
      idempotency_key: `manual-improvement:${promptId}:${versionId}:${crypto.randomUUID()}`,
    }),
    schema: agentRunSchema,
  });
}

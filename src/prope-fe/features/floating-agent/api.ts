import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import { agentRunSchema, floatingAgentEventSchema, type AgentRun, type FloatingAgentEvent } from '@/features/floating-agent/types';

function eventType(run: AgentRun): FloatingAgentEvent['type'] {
  if (run.status === 'queued' || run.status === 'running') return 'progress';
  if (run.status === 'succeeded') return 'success';
  return 'warning';
}

function resultAction(run: AgentRun): FloatingAgentEvent['action'] {
  const action = run.result_actions[0];
  if (!action) return undefined;
  if (action.kind === 'review_import' && action.batch_id) {
    return { labelKey: 'floatingAgent.actions.reviewImport', href: `/app/imports/${encodeURIComponent(action.batch_id)}` };
  }
  if (action.kind === 'open_evaluation' && run.prompt_id) {
    const version = run.version_id ? `&version=${encodeURIComponent(run.version_id)}` : '';
    return { labelKey: 'floatingAgent.actions.openEvaluation', href: `/app/prompts/${encodeURIComponent(run.prompt_id)}?tab=evaluation${version}` };
  }
  return undefined;
}

function toEvent(run: AgentRun): FloatingAgentEvent {
  const progress = run.progress_current !== null && run.progress_total !== null && run.progress_unit
    ? { current: run.progress_current, total: run.progress_total, unit: run.progress_unit }
    : undefined;
  return floatingAgentEventSchema.parse({
    id: run.run_id,
    runId: run.run_id,
    type: eventType(run),
    titleKey: `floatingAgent.kinds.${run.kind}.title`,
    messageKey: `floatingAgent.status.${run.status}`,
    progress,
    action: resultAction(run),
    dismissible: run.status !== 'queued' && run.status !== 'running',
  });
}

export async function getFloatingAgentEvents(): Promise<FloatingAgentEvent[]> {
  const runs = await apiRequest('/api/v1/agent-runs?limit=20', { schema: z.array(agentRunSchema) });
  return runs.filter((run) => run.acknowledged_at === null).map(toEvent);
}

export async function acknowledgeAgentRun(runId: string) {
  return apiRequest(`/api/v1/agent-runs/${encodeURIComponent(runId)}/acknowledge`, {
    method: 'POST',
    schema: agentRunSchema,
  });
}

export function getAgentRun(runId: string): Promise<AgentRun> {
  return apiRequest(`/api/v1/agent-runs/${encodeURIComponent(runId)}`, { schema: agentRunSchema });
}

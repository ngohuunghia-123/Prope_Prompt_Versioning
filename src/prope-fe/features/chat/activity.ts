import type { ChatActivity, TraceEntry } from '@/features/chat/types';

function activityMeta(entry: TraceEntry): Pick<ChatActivity, 'id' | 'kind' | 'label_code'> {
  if (entry.agent === 'guardrail.input') {
    return { id: 'guardrail.input', kind: 'thought', label_code: 'chat.activity.inspectRequest' };
  }
  if (entry.agent === 'supervisor' && entry.action === 'route') {
    return { id: 'supervisor.route', kind: 'thought', label_code: 'chat.activity.route' };
  }
  if (entry.agent.startsWith('worker.')) {
    return { id: entry.agent, kind: 'action', label_code: `chat.activity.tool.${entry.agent.slice(7)}` };
  }
  if (entry.agent === 'supervisor' && entry.action === 'respond') {
    return { id: 'supervisor.respond', kind: 'thought', label_code: 'chat.activity.compose' };
  }
  return { id: 'guardrail.output', kind: 'thought', label_code: 'chat.activity.verifySources' };
}

export function activitiesFromTrace(trace: TraceEntry[] = []): ChatActivity[] {
  return trace.map((entry) => ({
    ...activityMeta(entry),
    status: entry.status,
    latency_ms: entry.latency_ms,
  }));
}

export function mergeActivity(current: ChatActivity[], incoming: ChatActivity): ChatActivity[] {
  const index = current.findIndex((activity) => activity.id === incoming.id);
  if (index < 0) return [...current, incoming];
  return current.map((activity, activityIndex) => activityIndex === index ? incoming : activity);
}

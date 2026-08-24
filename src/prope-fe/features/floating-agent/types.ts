import { z } from 'zod';

export const agentRunStatusSchema = z.enum(['queued', 'running', 'waiting_for_user', 'succeeded', 'warning', 'failed', 'cancelled']);
export const agentRunKindSchema = z.enum(['chat', 'import', 'evaluation', 'production_analysis', 'improvement']);
export const agentNodeSchema = z.object({
  id: z.string(), sequence: z.number().int(), capability: z.string(),
  kind: z.enum(['llm', 'retrieval', 'automated_check', 'provider_call', 'human_decision']),
  status: z.string(), evidence_refs: z.array(z.string()).default([]),
  progress_current: z.number().int().nullable().default(null),
  progress_total: z.number().int().nullable().default(null),
  progress_unit: z.string().nullable().default(null),
  started_at: z.string().nullable().default(null), finished_at: z.string().nullable().default(null),
});
export const agentRunSchema = z.object({
  run_id: z.string(), kind: agentRunKindSchema,
  plan_basis: z.enum(['llm', 'explicit_user_action', 'schedule']), status: agentRunStatusSchema,
  prompt_id: z.string().nullable().default(null), version_id: z.string().nullable().default(null),
  source_refs: z.array(z.string()).default([]), result_actions: z.array(z.record(z.string(), z.string())).default([]),
  progress_current: z.number().int().nullable().default(null), progress_total: z.number().int().nullable().default(null),
  progress_unit: z.string().nullable().default(null), acknowledged_at: z.string().nullable().default(null),
  created_at: z.string(), updated_at: z.string(), started_at: z.string().nullable().default(null),
  finished_at: z.string().nullable().default(null), nodes: z.array(agentNodeSchema).default([]),
  edges: z.array(z.object({ source: z.string(), target: z.string() })).default([]),
});

export const floatingAgentEventTypeSchema = z.enum(['progress', 'attention', 'success', 'warning']);
export const floatingAgentEventSchema = z.object({
  id: z.string(), runId: z.string(), type: floatingAgentEventTypeSchema,
  titleKey: z.string(), messageKey: z.string(),
  progress: z.object({ current: z.number().int().nonnegative(), total: z.number().int().positive(), unit: z.string() }).optional(),
  action: z.object({ labelKey: z.string(), href: z.string() }).optional(),
  dismissible: z.boolean().default(true),
});

export type AgentRun = z.infer<typeof agentRunSchema>;
export type FloatingAgentEvent = z.infer<typeof floatingAgentEventSchema>;
export type FloatingAgentEventType = z.infer<typeof floatingAgentEventTypeSchema>;

const eventPriority: Record<FloatingAgentEventType, number> = { warning: 4, attention: 3, success: 2, progress: 1 };

export function selectFloatingAgentEvent(events: FloatingAgentEvent[]) {
  return [...events].sort((left, right) => eventPriority[right.type] - eventPriority[left.type])[0] ?? null;
}

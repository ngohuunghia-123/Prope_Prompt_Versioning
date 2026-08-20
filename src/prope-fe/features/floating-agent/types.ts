import { z } from 'zod';

export const floatingAgentEventTypeSchema = z.enum(['progress', 'success', 'warning', 'tip']);

export const floatingAgentEventSchema = z.object({
  id: z.string(),
  type: floatingAgentEventTypeSchema,
  titleKey: z.string(),
  messageKey: z.string(),
  progress: z.number().min(0).max(100).optional(),
  action: z.object({ labelKey: z.string(), href: z.string() }).optional(),
  dismissible: z.boolean().default(true),
});

export type FloatingAgentEvent = z.infer<typeof floatingAgentEventSchema>;
export type FloatingAgentEventType = z.infer<typeof floatingAgentEventTypeSchema>;

const eventPriority: Record<FloatingAgentEventType, number> = {
  warning: 4,
  success: 3,
  progress: 2,
  tip: 1,
};

export function selectFloatingAgentEvent(events: FloatingAgentEvent[]) {
  return [...events].sort((left, right) => eventPriority[right.type] - eventPriority[left.type])[0] ?? null;
}

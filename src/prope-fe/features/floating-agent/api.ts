import { z } from 'zod';
import { floatingAgentEventSchema, type FloatingAgentEvent } from '@/features/floating-agent/types';

const MOCK_DURATION_MS = 16_000;
let mockStartedAt: number | null = null;

/** Mock query-layer source; replace this function with the background-jobs endpoint later. */
export async function getFloatingAgentEvents(): Promise<FloatingAgentEvent[]> {
  mockStartedAt ??= Date.now();
  const elapsed = Date.now() - mockStartedAt;
  const progress = Math.min(100, Math.round((elapsed / MOCK_DURATION_MS) * 100));
  const events = progress < 100
    ? [
        {
          id: 'mock-eval-running',
          type: 'progress' as const,
          titleKey: 'floatingAgent.events.evalRunning.title',
          messageKey: 'floatingAgent.events.evalRunning.message',
          progress,
          dismissible: false,
        },
        {
          id: 'mock-tip',
          type: 'tip' as const,
          titleKey: 'floatingAgent.events.tip.title',
          messageKey: 'floatingAgent.events.tip.message',
          dismissible: true,
        },
      ]
    : [
        {
          id: 'mock-eval-complete',
          type: 'success' as const,
          titleKey: 'floatingAgent.events.evalComplete.title',
          messageKey: 'floatingAgent.events.evalComplete.message',
          action: { labelKey: 'floatingAgent.events.evalComplete.action', href: '/app/prompts' },
          dismissible: true,
        },
        {
          id: 'mock-tip',
          type: 'tip' as const,
          titleKey: 'floatingAgent.events.tip.title',
          messageKey: 'floatingAgent.events.tip.message',
          dismissible: true,
        },
      ];

  return z.array(floatingAgentEventSchema).parse(events);
}

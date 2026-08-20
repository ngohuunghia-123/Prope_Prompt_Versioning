import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FloatingAgentContext, type FloatingAgentContextValue } from '@/features/floating-agent/FloatingAgentContext';
import { floatingAgentEventsOptions } from '@/features/floating-agent/queries';
import { selectFloatingAgentEvent, type FloatingAgentEvent } from '@/features/floating-agent/types';

const VISIBILITY_KEY = 'prope-floating-agent-visible';
const EXPANDED_KEY = 'prope-floating-agent-expanded';
const loadingEvent: FloatingAgentEvent = {
  id: 'floating-agent-loading', type: 'progress', titleKey: 'floatingAgent.events.loading.title',
  messageKey: 'floatingAgent.events.loading.message', dismissible: false,
};
const errorEvent: FloatingAgentEvent = {
  id: 'floating-agent-error', type: 'warning', titleKey: 'floatingAgent.events.error.title',
  messageKey: 'floatingAgent.events.error.message', dismissible: true,
};

function readBoolean(key: string, fallback: boolean) {
  const stored = window.localStorage.getItem(key);
  return stored === null ? fallback : stored === 'true';
}

export function FloatingAgentProvider({ children }: { children: ReactNode }) {
  const eventsQuery = useQuery(floatingAgentEventsOptions);
  const [visible, setVisibleState] = useState(() => readBoolean(VISIBILITY_KEY, true));
  const [expanded, setExpandedState] = useState(() => readBoolean(EXPANDED_KEY, true));
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const events = useMemo(() => {
    const source = eventsQuery.isPending ? [loadingEvent] : eventsQuery.isError ? [errorEvent] : (eventsQuery.data ?? []);
    return source.filter((event) => !dismissed.has(event.id));
  }, [dismissed, eventsQuery.data, eventsQuery.isError, eventsQuery.isPending]);
  const activeEvent = useMemo(() => selectFloatingAgentEvent(events), [events]);
  const runningCount = events.filter((event) => event.type === 'progress').length;

  const setVisible = useCallback((next: boolean) => {
    setVisibleState(next);
    window.localStorage.setItem(VISIBILITY_KEY, String(next));
  }, []);
  const toggleVisible = useCallback(() => setVisible(!visible), [setVisible, visible]);
  const setExpanded = useCallback((next: boolean) => {
    setExpandedState(next);
    window.localStorage.setItem(EXPANDED_KEY, String(next));
  }, []);
  const dismiss = useCallback((eventId: string) => {
    setDismissed((current) => new Set(current).add(eventId));
  }, []);

  const value = useMemo<FloatingAgentContextValue>(() => ({
    visible, expanded, activeEvent, runningCount, setVisible, toggleVisible, setExpanded, dismiss,
  }), [activeEvent, dismiss, expanded, runningCount, setExpanded, setVisible, toggleVisible, visible]);

  return <FloatingAgentContext.Provider value={value}>{children}</FloatingAgentContext.Provider>;
}

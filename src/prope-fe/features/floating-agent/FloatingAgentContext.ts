import { createContext, useContext } from 'react';
import type { FloatingAgentEvent } from '@/features/floating-agent/types';

export interface FloatingAgentContextValue {
  visible: boolean;
  expanded: boolean;
  activeEvent: FloatingAgentEvent | null;
  events: FloatingAgentEvent[];
  runningCount: number;
  setVisible: (visible: boolean) => void;
  toggleVisible: () => void;
  setExpanded: (expanded: boolean) => void;
  dismiss: (eventId: string) => void;
}

export const FloatingAgentContext = createContext<FloatingAgentContextValue | null>(null);

export function useFloatingAgent() {
  const value = useContext(FloatingAgentContext);
  if (!value) throw new Error('useFloatingAgent must be used within FloatingAgentProvider');
  return value;
}

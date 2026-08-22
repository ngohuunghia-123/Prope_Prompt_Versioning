import { createContext, useContext } from 'react';
import type { UiDirective } from '@/features/chat/types';

/**
 * The interface state the assistant is allowed to drive, and nothing else.
 *
 * **Why a context and not a router push per directive.** Three of the seven
 * directive kinds — `prefill_form`, `set_step`, `highlight` — are not
 * navigations at all: they are *state a page reads when it renders*. Pushing
 * them through the URL would put a converted prompt body in a query string, and
 * firing them as DOM side effects would make them untestable and unorderable.
 * A context is what lets `navigate` change the route and the other three arrive
 * at the destination already set.
 *
 * **Every field here is cleared by somebody.** `highlight` expires on a timer,
 * `dialog` is consumed by whichever component opens it, and `prefill` is cleared
 * by the form that reads it. State the assistant set and nobody clears is state
 * that reappears three navigations later with no explanation.
 */
export interface AgentSurfaceState {
  /** True only while a direct navigate/prefill/dialog instruction is applied. */
  interacting: boolean;
  /** The import stepper the chat drives: `paste | convert | duplicates | review | save`. */
  step: string | null;
  /** A region to draw attention to, cleared after a few seconds. */
  highlight: string | null;
  /** A dialog to open once. The opener consumes it. */
  dialog: string | null;
  /** A tab to select on the page the person landed on. */
  tab: string | null;
  /** `form name -> field values`. Written into controlled inputs, never submitted. */
  prefill: { form: string; fields: Record<string, string> } | null;
}

export const EMPTY_SURFACE: AgentSurfaceState = {
  interacting: false,
  step: null,
  highlight: null,
  dialog: null,
  tab: null,
  prefill: null,
};

export interface AgentSurfaceContextValue extends AgentSurfaceState {
  /** Apply a validated batch. Called only by the chat hook, never by a page. */
  apply: (directives: UiDirective[]) => void;
  clearDialog: () => void;
  clearPrefill: () => void;
  clearHighlight: () => void;
}

export const AgentSurfaceContext = createContext<AgentSurfaceContextValue | null>(null);

/**
 * What a page calls to find out whether the assistant asked for anything.
 *
 * Returns the empty surface outside the provider rather than throwing, so a
 * component can be rendered in the component lab or a test without the whole
 * chat stack around it. A page that reads `null` behaves exactly as it did
 * before the assistant existed, which is the correct default for a feature that
 * is an accelerator rather than a dependency.
 */
export function useAgentSurface(): AgentSurfaceState & { clearDialog: () => void; clearPrefill: () => void } {
  const value = useContext(AgentSurfaceContext);
  if (!value) return { ...EMPTY_SURFACE, clearDialog: () => {}, clearPrefill: () => {} };
  // `apply` and `clearHighlight` stay behind: a page may read the surface and
  // clear what it consumed, but only the chat hook decides what goes on it.
  return {
    step: value.step,
    interacting: value.interacting,
    highlight: value.highlight,
    dialog: value.dialog,
    tab: value.tab,
    prefill: value.prefill,
    clearDialog: value.clearDialog,
    clearPrefill: value.clearPrefill,
  };
}

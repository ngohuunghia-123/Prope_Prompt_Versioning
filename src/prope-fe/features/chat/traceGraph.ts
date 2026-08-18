import type { NodeState, Pipeline, PipelineNode, TraceEntry } from '@/features/chat/types';

/**
 * Turning one turn's trace into a state for every node the assistant *could*
 * have visited.
 *
 * Pure, and in its own module rather than inside the component, because the
 * interesting half of this feature is the reasoning about absence and that half
 * is worth testing without a DOM.
 *
 * **The whole problem is that a missing trace entry means two opposite things.**
 * The router picking three tools out of six leaves three nodes with no entry;
 * an input rail refusing the question leaves nine. Both look identical from the
 * trace alone — an agent name that never appears — and only one of them is ever
 * a bug. `reachedStage` below is what separates them: a node earlier than the
 * furthest point the turn got to was *considered and declined*, a node beyond it
 * was never put the question.
 */

/** Worst-first. A node that ran twice is reported as its worst outcome, never its last. */
const SEVERITY: Record<NodeState, number> = {
  error: 5,
  refused: 4,
  warn: 3,
  ok: 2,
  'not-chosen': 1,
  unreached: 0,
};

export interface NodeVisit {
  node: PipelineNode;
  state: NodeState;
  /** Summed over every matching entry. Null when the node did not run. */
  latencyMs: number | null;
  /** How many trace entries matched. Above one only when a plan named a tool twice. */
  visits: number;
}

/**
 * Whether a trace entry belongs to a node.
 *
 * `agent` first, then `action` when the node names one. Only the supervisor
 * names one, because it is the only agent that appears at two different stages
 * of the same turn — routing and answering — and a graph that lit up both boxes
 * for one of them would be worse than no graph.
 */
function matches(node: PipelineNode, entry: TraceEntry): boolean {
  if (entry.agent !== node.agent) return false;
  return node.action === null || node.action === entry.action;
}

/**
 * The catalogue key for one trace entry, resolved through the pipeline.
 *
 * Used by the flat trace list, which has an entry and wants a Vietnamese label.
 * It goes through the same {@link matches} rule the graph uses rather than
 * deriving a key from the agent name, so there is exactly one place that knows
 * how an entry becomes a node — and no copy of the server's rule to go stale.
 *
 * Returns null when the pipeline has not arrived, or for an entry from an older
 * stored turn whose agent no longer exists. The caller falls back to the raw
 * name, which is ugly and true.
 */
export function labelCodeFor(pipeline: Pipeline | undefined, entry: TraceEntry): string | null {
  return pipeline?.nodes.find((node) => matches(node, entry))?.label_code ?? null;
}

/**
 * What one entry says happened.
 *
 * `detail.outcome` is checked before `status` and that order is the point: a
 * permission refusal arrives as `status: 'error'` with `outcome: 'refused'`,
 * because the orchestrator has only three status values and refusal is not one
 * of them. Reading the status alone would paint "you may not do that" in the
 * same colour as "this crashed", which the server's own metrics go out of their
 * way to keep apart.
 */
function stateOf(entry: TraceEntry): NodeState {
  if (entry.detail?.outcome === 'refused') return 'refused';
  if (entry.status === 'error') return 'error';
  if (entry.status === 'warn') return 'warn';
  return 'ok';
}

export function readNodeStates(pipeline: Pipeline, trace: TraceEntry[]): NodeVisit[] {
  const matched = new Map<string, TraceEntry[]>();
  for (const node of pipeline.nodes) {
    const entries = trace.filter((entry) => matches(node, entry));
    if (entries.length) matched.set(node.id, entries);
  }

  // The furthest stage anything actually ran at. -1 when the trace is empty,
  // which makes every node `unreached` — correct for a turn that never started.
  const reachedStage = pipeline.nodes.reduce(
    (furthest, node) => (matched.has(node.id) ? Math.max(furthest, node.stage) : furthest),
    -1,
  );

  return pipeline.nodes.map((node) => {
    const entries = matched.get(node.id);
    if (!entries) {
      return {
        node,
        state: node.stage > reachedStage ? 'unreached' : 'not-chosen',
        latencyMs: null,
        visits: 0,
      };
    }
    const state = entries
      .map(stateOf)
      .reduce((worst, next) => (SEVERITY[next] > SEVERITY[worst] ? next : worst));
    return {
      node,
      state,
      latencyMs: entries.reduce((total, entry) => total + entry.latency_ms, 0),
      visits: entries.length,
    };
  });
}

/** Nodes grouped by stage, stages in order. The stacking a caller draws as a column. */
export function byStage(visits: NodeVisit[]): NodeVisit[][] {
  const stages = [...new Set(visits.map((visit) => visit.node.stage))].sort((a, b) => a - b);
  return stages.map((stage) => visits.filter((visit) => visit.node.stage === stage));
}

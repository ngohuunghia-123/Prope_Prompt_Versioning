import type { ConversationGraph, ConversationNode } from '@/features/prompt-lifecycle/insightsTypes';

/**
 * Turning a flat list of calls into the tree the customer's application ran.
 *
 * Pure functions over the response — no React, no fetching, no formatting. The
 * component that draws the picture decides pixels; everything about *what the
 * shape is* lives here, so it can be reasoned about (and tested) without a DOM.
 *
 * **The server has already cut every edge that lands on a node this reader may
 * not see**, and this file must not try to repair one. A node whose parent is
 * missing is a root. Whether that parent was hidden, expired, or never existed
 * is deliberately unknowable here — and re-attaching such a node to its
 * grandparent would draw a call that never happened.
 */

/** What happened at one step, folded from `outcome` into the four the picture distinguishes. */
export type NodeOutcome = 'ok' | 'fallback' | 'truncated' | 'error';

export interface PlacedNode {
  node: ConversationNode;
  /** How many steps from the head of its chain. The x-axis. */
  depth: number;
  outcome: NodeOutcome;
  /** Milliseconds the provider took. Null when the call never reached one. */
  durationMs: number | null;
}

export function outcomeOf(node: ConversationNode): NodeOutcome {
  if (node.outcome === 'caller_error' || node.outcome === 'upstream_error') return 'error';
  if (node.outcome === 'fallback') return 'fallback';
  if (node.outcome === 'truncated') return 'truncated';
  return 'ok';
}

/**
 * The chain, as columns of nodes left to right.
 *
 * Depth-first from each root in time order, so siblings stay adjacent and a
 * sub-agent's whole branch reads as one block rather than being interleaved with
 * its cousins by the clock.
 *
 * **A cycle cannot hang this.** The ledger refuses a call that is its own parent
 * and the caller supplies the rest, so `A → B → A` is a shape a buggy
 * integration can genuinely produce. Nodes still unseen once the walk finishes
 * are treated as roots, which draws the loop as several short chains — visibly
 * odd, which is the correct rendering of something that is in fact wrong.
 */
export function columnsOf(graph: ConversationGraph): PlacedNode[][] {
  const byId = new Map(graph.nodes.map((node) => [node.call_id, node]));
  const children = new Map<string, ConversationNode[]>();
  const roots: ConversationNode[] = [];

  for (const node of graph.nodes) {
    const parent = node.parent_call_id;
    if (parent === null || !byId.has(parent)) {
      roots.push(node);
      continue;
    }
    const siblings = children.get(parent);
    if (siblings) siblings.push(node);
    else children.set(parent, [node]);
  }

  const byTime = (a: ConversationNode, b: ConversationNode): number =>
    a.created_at === b.created_at
      ? a.call_id.localeCompare(b.call_id)
      : a.created_at.localeCompare(b.created_at);

  const columns: PlacedNode[][] = [];
  const seen = new Set<string>();

  const walk = (node: ConversationNode, depth: number): void => {
    if (seen.has(node.call_id)) return;
    seen.add(node.call_id);
    (columns[depth] ??= []).push({
      node,
      depth,
      outcome: outcomeOf(node),
      durationMs: node.upstream_duration_ms,
    });
    for (const child of (children.get(node.call_id) ?? []).sort(byTime)) walk(child, depth + 1);
  };

  for (const root of [...roots].sort(byTime)) walk(root, 0);
  // Anything left is in a cycle. Drawn as its own chain rather than dropped:
  // the calls did happen, and only the links between them are nonsense.
  //
  // Copied before sorting, here and above. `sort` is in place, and `graph.nodes`
  // is React Query's cached response — sorting it would reorder the array every
  // other reader of that cache entry sees, from inside what is meant to be a
  // pure derivation.
  for (const node of [...graph.nodes].sort(byTime)) walk(node, 0);

  return columns.map((column) => column ?? []);
}

/**
 * True when a conversation is a straight line — every node has at most one child.
 *
 * The common case, and worth knowing: a line reads perfectly well as a list, so
 * a caller who has not threaded `parent_call_id` at all still gets something
 * useful rather than a column of disconnected boxes pretending to be a graph.
 */
export function isLinear(columns: PlacedNode[][]): boolean {
  return columns.every((column) => column.length <= 1);
}

/** How many of the calls in this chain failed. What the list column counts. */
export function errorCount(graph: ConversationGraph): number {
  return graph.nodes.filter((node) => outcomeOf(node) === 'error').length;
}

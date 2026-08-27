/**
 * Line-level filtering inside one block, for "only show changes".
 *
 * Block state alone is the wrong granularity to hang that control on, and the
 * canonical prompt contract is why. `canonical_prompt.validate_canonical_xml`
 * accepts a stored body in exactly two shapes: named blocks drawn from a fixed
 * vocabulary, or the nameless `<>` wrapper, which holds the whole prompt as ONE
 * block. Every prompt whose author declined the XML conversion is the second
 * shape — so "only show changes" had a single block to filter and could do one
 * of two things with it, keep all of it or hide all of it, neither of which is
 * what a person means by the phrase. From their seat the checkbox did nothing.
 *
 * So the filter reaches inside a changed block and keeps the lines that differ,
 * with a line of context either side and a count standing in for the rest.
 *
 * The match is by LINE and by longest common subsequence rather than by
 * position, because a positional walk reports every line after an insertion as
 * changed — which on a prompt, where inserting one instruction near the top is
 * the ordinary edit, degrades straight back to showing everything.
 */

/** Lines of context kept either side of a change, so a kept line has a place. */
const CONTEXT_LINES = 1;

/**
 * How many lines a run must hide before collapsing it is worth a row of its
 * own. Replacing two lines with "… 2 unchanged lines" saves nothing and costs
 * the reader the two lines.
 */
const MIN_COLLAPSED_LINES = 2;

/**
 * Past this, both sides are shown in full instead.
 *
 * The table below is O(before × after), which is nothing at prompt sizes — the
 * registry caps a body at 32,768 characters — but the bound is what keeps a
 * pathological body from being a page that locks the tab, and showing an
 * unfiltered diff is a worse answer than showing no diff at all.
 */
const MAX_DIFF_LINES = 400;

type LineOp = { type: 'same' | 'removed' | 'added'; text: string };

export type DiffRow =
  | { kind: 'line'; text: string; changed: boolean }
  | { kind: 'gap'; hidden: number };

export interface ChangedLinesView {
  before: DiffRow[];
  after: DiffRow[];
}

/** Longest common subsequence of two line arrays, as a flat op list. */
function lineOps(before: string[], after: string[]): LineOp[] {
  const table: number[][] = Array.from({ length: before.length + 1 }, () => new Array<number>(after.length + 1).fill(0));
  for (let i = before.length - 1; i >= 0; i -= 1) {
    for (let j = after.length - 1; j >= 0; j -= 1) {
      table[i]![j] = before[i] === after[j] ? table[i + 1]![j + 1]! + 1 : Math.max(table[i + 1]![j]!, table[i]![j + 1]!);
    }
  }
  const ops: LineOp[] = [];
  let i = 0;
  let j = 0;
  while (i < before.length && j < after.length) {
    if (before[i] === after[j]) {
      ops.push({ type: 'same', text: before[i]! });
      i += 1;
      j += 1;
    } else if (table[i + 1]![j]! >= table[i]![j + 1]!) {
      ops.push({ type: 'removed', text: before[i]! });
      i += 1;
    } else {
      ops.push({ type: 'added', text: after[j]! });
      j += 1;
    }
  }
  for (; i < before.length; i += 1) ops.push({ type: 'removed', text: before[i]! });
  for (; j < after.length; j += 1) ops.push({ type: 'added', text: after[j]! });
  return ops;
}

/**
 * Which ops are worth showing: the changed ones and their neighbours.
 *
 * Computed once over the whole op list rather than per pane, because a pure
 * insertion changes nothing on the old side — and a left pane whose context
 * came only from its own changes would have none, collapsing to a bare "…"
 * with nothing to read the insertion against.
 */
function keptOps(ops: LineOp[]): boolean[] {
  const changed = ops.map((op) => op.type !== 'same');
  return ops.map((_, index) => {
    const last = Math.min(changed.length - 1, index + CONTEXT_LINES);
    for (let near = Math.max(0, index - CONTEXT_LINES); near <= last; near += 1) {
      if (changed[near]) return true;
    }
    return false;
  });
}

/** One pane's rows: its own lines, with the runs nobody needs collapsed. */
function paneRows(ops: LineOp[], kept: boolean[], own: 'removed' | 'added'): DiffRow[] {
  const lines = ops
    .map((op, index) => ({ op, kept: kept[index]! }))
    .filter((line) => line.op.type === 'same' || line.op.type === own);

  const rows: DiffRow[] = [];
  let index = 0;
  while (index < lines.length) {
    if (lines[index]!.kept) {
      rows.push({ kind: 'line', text: lines[index]!.op.text, changed: lines[index]!.op.type !== 'same' });
      index += 1;
      continue;
    }
    let end = index;
    while (end < lines.length && !lines[end]!.kept) end += 1;
    if (end - index > MIN_COLLAPSED_LINES) {
      rows.push({ kind: 'gap', hidden: end - index });
    } else {
      for (let shown = index; shown < end; shown += 1) rows.push({ kind: 'line', text: lines[shown]!.op.text, changed: false });
    }
    index = end;
  }
  return rows;
}

/**
 * The two panes of one changed block, reduced to what differs.
 *
 * `null` means *do not filter this one* — the block is past `MAX_DIFF_LINES`,
 * or nothing in it actually differs line by line, and in both cases the honest
 * thing to render is the block as it stands.
 */
export function changedLinesOnly(before: string, after: string): ChangedLinesView | null {
  const beforeLines = before.split('\n');
  const afterLines = after.split('\n');
  if (beforeLines.length > MAX_DIFF_LINES || afterLines.length > MAX_DIFF_LINES) return null;
  const ops = lineOps(beforeLines, afterLines);
  if (!ops.some((op) => op.type !== 'same')) return null;
  const kept = keptOps(ops);
  return { before: paneRows(ops, kept, 'removed'), after: paneRows(ops, kept, 'added') };
}

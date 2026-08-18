import { useTranslation } from 'react-i18next';

import { byStage, readNodeStates, type NodeVisit } from '@/features/chat/traceGraph';
import type { NodeState, Pipeline, TraceEntry } from '@/features/chat/types';
import { cn } from '@/lib/cn';

/**
 * One turn, drawn as the pipeline it walked through.
 *
 * **Every node the assistant could have visited is drawn, including the ones it
 * did not.** That is the whole reason this exists next to a trace list that
 * already says what ran: the list can tell you the assistant answered from the
 * documentation, and it cannot tell you it considered searching your prompts and
 * decided against it. A picture of only what happened has no way to show a road
 * not taken.
 *
 * **Edges and columns come from the server, positions come from here.** The
 * response says this node is the third of five things that happen; how far along
 * the x-axis that lands is a rendering question and stays in this file. The
 * consequence that matters: a seventh tool added to `domain.TOOLS` appears in
 * this graph with no change to this component.
 *
 * **Nodes are HTML over an SVG, not SVG text.** SVG has no text truncation and
 * no wrapping, and these labels are Vietnamese words of unpredictable length. So
 * the SVG layer draws edges — the one thing HTML is bad at — and the boxes are
 * divs, which brings truncation, `title`, focus rings and the design tokens with
 * them.
 *
 * **State is never colour alone.** Every box carries its state in words as well
 * as in fill, because six states separated only by hue is a graph that stops
 * working for the people most likely to be reading it carefully.
 */

const NODE_W = 172;
const NODE_H = 48;
const COL_GAP = 56;
const ROW_GAP = 12;
const PAD = 14;

const COL_PITCH = NODE_W + COL_GAP;
const ROW_PITCH = NODE_H + ROW_GAP;

/** Fill, border and text per state. `unreached` is also dimmed — it is the absence of a fact. */
const STATE_STYLE: Record<NodeState, string> = {
  ok: 'border-border-success bg-success text-success-text',
  warn: 'border-warning-strong bg-warning text-warning-text',
  error: 'border-danger-strong bg-danger text-danger-text',
  refused: 'border-warning-strong border-dashed bg-canvas text-warning-text',
  'not-chosen': 'border-border bg-canvas text-muted',
  unreached: 'border-border-disabled border-dashed bg-canvas text-muted opacity-60',
};

const STATES: NodeState[] = ['ok', 'warn', 'error', 'refused', 'not-chosen', 'unreached'];

/** A node counts as having run for edge-liveness. Refusals and errors ran; absences did not. */
function ran(visit: NodeVisit): boolean {
  return visit.state !== 'not-chosen' && visit.state !== 'unreached';
}

interface Placed {
  visit: NodeVisit;
  x: number;
  y: number;
}

export function TraceGraph({ pipeline, trace }: { pipeline: Pipeline; trace: TraceEntry[] }) {
  const { t } = useTranslation();

  const columns = byStage(readNodeStates(pipeline, trace));
  const rows = Math.max(...columns.map((column) => column.length), 1);
  const width = columns.length * COL_PITCH - COL_GAP + PAD * 2;
  const height = rows * ROW_PITCH - ROW_GAP + PAD * 2;

  // Each column is centred against the tallest one, so a five-stage pipeline
  // whose middle stage holds six workers reads as a spindle rather than a
  // staircase — the fixed stages stay on one line through the middle.
  const placed = new Map<string, Placed>();
  columns.forEach((column, columnIndex) => {
    const columnHeight = column.length * ROW_PITCH - ROW_GAP;
    const top = PAD + (height - PAD * 2 - columnHeight) / 2;
    column.forEach((visit, rowIndex) => {
      placed.set(visit.node.id, {
        visit,
        x: PAD + columnIndex * COL_PITCH,
        y: top + rowIndex * ROW_PITCH,
      });
    });
  });

  return (
    <div className="grid gap-3">
      <div className="overflow-x-auto">
        <div className="relative" style={{ width, height }}>
          <svg width={width} height={height} aria-hidden className="absolute inset-0">
            {pipeline.edges.map((edge) => {
              const source = placed.get(edge.source);
              const target = placed.get(edge.target);
              if (!source || !target) return null;
              const x1 = source.x + NODE_W;
              const y1 = source.y + NODE_H / 2;
              const x2 = target.x;
              const y2 = target.y + NODE_H / 2;
              const bend = Math.max(18, (x2 - x1) / 2);
              const live = ran(source.visit) && ran(target.visit);
              return (
                <path
                  key={`${edge.source}->${edge.target}`}
                  d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  className={live ? 'stroke-border-strong' : 'stroke-border-disabled'}
                  strokeWidth={live ? 1.75 : 1}
                />
              );
            })}
          </svg>
          <ol className="m-0 list-none p-0">
            {[...placed.values()].map(({ visit, x, y }) => {
              const label = t(visit.node.label_code, { defaultValue: visit.node.id });
              const state = t(`chat.graph.state.${visit.state}`);
              return (
                <li
                  key={visit.node.id}
                  style={{ left: x, top: y, width: NODE_W, height: NODE_H }}
                  className="absolute"
                >
                  <div
                    title={`${label} · ${state}`}
                    className={cn(
                      'grid h-full content-center gap-0.5 rounded-navigation-panel border px-2 py-1',
                      STATE_STYLE[visit.state],
                    )}
                  >
                    <span className="truncate text-caption font-semibold">{label}</span>
                    <span className="flex items-baseline justify-between gap-1.5 text-overline">
                      <span className="truncate">{state}</span>
                      {visit.latencyMs === null ? null : (
                        <span className="shrink-0 tabular-nums">{visit.latencyMs}ms</span>
                      )}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
      <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {STATES.map((state) => (
          <li
            key={state}
            className={cn('rounded-full border px-1.5 py-0.5 text-overline', STATE_STYLE[state])}
          >
            {t(`chat.graph.state.${state}`)}
          </li>
        ))}
      </ul>
    </div>
  );
}

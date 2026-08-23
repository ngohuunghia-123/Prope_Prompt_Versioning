import { useTranslation } from 'react-i18next';

import { columnsOf, type NodeOutcome, type PlacedNode } from '@/features/prompt-lifecycle/conversationGraph';
import type { ConversationGraph } from '@/features/prompt-lifecycle/insightsTypes';
import { cn } from '@/lib/cn';

/**
 * One end-user conversation, drawn as the chain of prompts it actually ran.
 *
 * **This is the customer's application, not Prope's pipeline.** Each box is one
 * of their own published prompts — a system prompt, a guardrail, a tool
 * definition, a sub-agent — served through the gateway, and the arrows are the
 * order their app called them in. Prope knows the order because the app said so:
 * `prope.conversation_id` groups the calls and `prope.parent_call_id` links them.
 *
 * **What is deliberately absent.** No message text: `ledger.call_body` has no
 * read path, so this draws the shape of a chain and never its content. And no
 * node for anything that did not go through the gateway — a tool *execution*, a
 * retrieval, a regex guardrail all happen inside the customer's own process,
 * where Prope never sees them. A gap between two boxes is therefore ordinary,
 * and the description below says so, because a reader who read the gaps as
 * missing data would go hunting for a bug that is not there.
 *
 * **Nodes are HTML over an SVG**, for `TraceGraph`'s reason: SVG has no text
 * truncation, and a prompt title is whatever the customer named their prompt.
 * The SVG layer draws the edges, which is the one thing HTML is bad at.
 *
 * **Outcome is never colour alone** — every box prints its outcome in words.
 */

const NODE_W = 188;
const NODE_H = 56;
const COL_GAP = 52;
const ROW_GAP = 14;
const PAD = 14;

const COL_PITCH = NODE_W + COL_GAP;
const ROW_PITCH = NODE_H + ROW_GAP;

const OUTCOME_STYLE: Record<NodeOutcome, string> = {
  ok: 'border-border-success bg-success text-success-text',
  fallback: 'border-warning-strong bg-warning text-warning-text',
  truncated: 'border-warning-strong border-dashed bg-canvas text-warning-text',
  error: 'border-danger-strong bg-danger text-danger-text',
};

const OUTCOMES: NodeOutcome[] = ['ok', 'fallback', 'truncated', 'error'];

interface Placed {
  placed: PlacedNode;
  x: number;
  y: number;
}

export function ConversationGraphView({ graph }: { graph: ConversationGraph }) {
  const { t } = useTranslation();

  const columns = columnsOf(graph);
  if (!columns.length) {
    return (
      <p className="p-6 text-center text-body text-muted">
        {t('lifecycle.insights.conversations.emptyGraph')}
      </p>
    );
  }

  const rows = Math.max(...columns.map((column) => column.length), 1);
  const width = columns.length * COL_PITCH - COL_GAP + PAD * 2;
  const height = rows * ROW_PITCH - ROW_GAP + PAD * 2;

  // Each column centred against the tallest, so a chain that fans out to two
  // sub-agents and comes back reads as a spindle rather than a staircase.
  const positions = new Map<string, Placed>();
  columns.forEach((column, columnIndex) => {
    const columnHeight = column.length * ROW_PITCH - ROW_GAP;
    const top = PAD + (height - PAD * 2 - columnHeight) / 2;
    column.forEach((placed, rowIndex) => {
      positions.set(placed.node.call_id, {
        placed,
        x: PAD + columnIndex * COL_PITCH,
        y: top + rowIndex * ROW_PITCH,
      });
    });
  });

  return (
    <div className="grid gap-3">
      <p className="text-caption text-muted">{t('lifecycle.insights.conversations.graphNote')}</p>

      <div className="overflow-x-auto">
        <div className="relative" style={{ width, height }}>
          <svg width={width} height={height} aria-hidden className="absolute inset-0">
            {[...positions.values()].map(({ placed, x, y }) => {
              const parentId = placed.node.parent_call_id;
              const parent = parentId === null ? undefined : positions.get(parentId);
              if (!parent) return null;
              const x1 = parent.x + NODE_W;
              const y1 = parent.y + NODE_H / 2;
              const x2 = x;
              const y2 = y + NODE_H / 2;
              const bend = Math.max(18, (x2 - x1) / 2);
              return (
                <path
                  key={placed.node.call_id}
                  d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  className="stroke-border-strong"
                  strokeWidth={1.75}
                />
              );
            })}
          </svg>
          <ol className="m-0 list-none p-0">
            {[...positions.values()].map(({ placed, x, y }) => {
              const { node } = placed;
              const title = node.prompt_title ?? t('lifecycle.insights.conversations.unnamedPrompt');
              const outcome = t(`lifecycle.insights.conversations.outcome.${placed.outcome}`);
              const revision =
                node.revision_number === null
                  ? null
                  : t('lifecycle.insights.conversations.revision', { number: node.revision_number });
              return (
                <li
                  key={node.call_id}
                  style={{ left: x, top: y, width: NODE_W, height: NODE_H }}
                  className="absolute"
                >
                  <div
                    title={[title, revision, outcome].filter(Boolean).join(' · ')}
                    className={cn(
                      'grid h-full content-center gap-0.5 rounded-navigation-panel border px-2 py-1',
                      OUTCOME_STYLE[placed.outcome],
                    )}
                  >
                    <span className="truncate text-caption font-semibold">{title}</span>
                    <span className="flex items-baseline justify-between gap-1.5 text-overline">
                      <span className="truncate">
                        {revision ? `${revision} · ${outcome}` : outcome}
                      </span>
                      {placed.durationMs === null ? null : (
                        <span className="shrink-0 tabular-nums">{placed.durationMs}ms</span>
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
        {OUTCOMES.map((outcome) => (
          <li
            key={outcome}
            className={cn('rounded-full border px-1.5 py-0.5 text-overline', OUTCOME_STYLE[outcome])}
          >
            {t(`lifecycle.insights.conversations.outcome.${outcome}`)}
          </li>
        ))}
      </ul>

      {/* Both notes are about honesty rather than decoration. `hidden_count`
          says a permissions gap is a permissions gap and not an application bug;
          `truncated` stops a partial picture reading as a complete one. */}
      {graph.hidden_count > 0 ? (
        <p className="text-caption text-warning-text">
          {t('lifecycle.insights.conversations.hidden', { count: graph.hidden_count })}
        </p>
      ) : null}
      {graph.truncated ? (
        <p className="text-caption text-warning-text">
          {t('lifecycle.insights.conversations.truncated')}
        </p>
      ) : null}
    </div>
  );
}

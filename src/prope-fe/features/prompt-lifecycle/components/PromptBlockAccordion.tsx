import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { cn } from '@/lib/cn';
import { WordHeatmap } from '@/features/prompt-lifecycle/components/WordHeatmap';
import { diffPromptBlocks } from '@/features/prompt-lifecycle/promptBlockDiff';
import { changedLinesOnly, type DiffRow } from '@/features/prompt-lifecycle/promptLineDiff';
import { VERBATIM_TAG } from '@/features/prompt-lifecycle/xmlBlocks';
import { sharedWordsOf } from '@/features/prompt-lifecycle/wordOverlap';

interface PromptBlockAccordionProps {
  beforeBody?: string;
  body: string;
  onlyChanged?: boolean;
  sideBySide?: boolean;
  /** Every block starts open, regardless of diff state. */
  defaultExpanded?: boolean;
}

const tagState = { added: 'success', changed: 'warning', unchanged: 'neutral', removed: 'danger' } as const;

interface BlockPaneProps {
  rows: DiffRow[];
  sharedWords: Set<string> | undefined;
}

/** One pane of a changed block, filtered down to the lines that differ. */
function FilteredPane({ rows, sharedWords }: BlockPaneProps) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-0.5">
      {rows.map((row, index) =>
        row.kind === 'gap' ? (
          <p key={`gap-${index}`} className="py-1 text-caption text-muted">
            {t('lifecycle.promptDetail.hiddenLines', { count: row.hidden })}
          </p>
        ) : sharedWords ? (
          <WordHeatmap
            key={`line-${index}`}
            text={row.text || ' '}
            sharedWords={sharedWords}
            className={cn('rounded px-1 font-mono text-caption', row.changed && 'bg-warning')}
          />
        ) : (
          <pre key={`line-${index}`} className={cn('whitespace-pre-wrap rounded px-1 font-mono text-caption text-ink', row.changed && 'bg-warning')}>
            {row.text || ' '}
          </pre>
        ),
      )}
    </div>
  );
}

export function PromptBlockAccordion({ beforeBody = '', body, onlyChanged = false, sideBySide = false, defaultExpanded = false }: PromptBlockAccordionProps) {
  const { t } = useTranslation();
  // A block the body no longer has is not part of the body, and `sideBySide` is
  // what separates the two things this component renders. With it, the panel is
  // a comparison, and a removal belongs in it — a reviewer deciding on a
  // revision has to see that `<safety>` went away, and it shows on the left,
  // where the old side is. Without it the panel is the body itself, under a
  // heading that says so, and a deleted block sitting there wearing a tag is
  // text this revision does not contain: it has no `after`, so it falls back to
  // rendering its `before`, putting a paragraph on the page that no call will
  // ever send. The copy button beside that heading already omits it.
  const blocks = diffPromptBlocks(beforeBody, body).filter(
    (block) => (sideBySide || block.state !== 'removed') && (!onlyChanged || block.state !== 'unchanged'),
  );
  const heatByBlockKey = useMemo(() => {
    const heat = new Map<string, Set<string>>();
    for (const block of blocks) {
      if (block.state === 'changed' && block.before !== null && block.after !== null) {
        heat.set(block.key, sharedWordsOf(block.before, block.after));
      }
    }
    return heat;
  }, [blocks]);
  if (blocks.length === 0) {
    // A filter that leaves nothing must say so. A panel that simply goes blank
    // is indistinguishable from one that failed to load, which is how a working
    // control gets read as a broken one.
    return <p className="rounded-xl border border-border bg-surface p-4 text-body text-muted">{t('lifecycle.promptDetail.noBlockChanges')}</p>;
  }

  return (
    <div className="grid gap-2">
      {blocks.map((block) => {
        const sharedWords = sideBySide ? heatByBlockKey.get(block.key) : undefined;
        // The filter reaches inside a changed block, not just around it: on a
        // one-block body — the `<>` form, which is most prompts — filtering
        // whole blocks is a control with one block to hide and nothing to show.
        const lines = onlyChanged && block.state === 'changed' && block.before !== null && block.after !== null
          ? changedLinesOnly(block.before, block.after)
          : null;
        return (
          <details key={block.key} open={defaultExpanded || block.state !== 'unchanged'} className="group overflow-hidden rounded-xl border border-border bg-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 focus-visible:outline-2 focus-visible:outline-focus">
              {/* Same rule as the editor card: a body kept whole is named, not
                  shown as `<>`. This one also renders a prompt's history, so it
                  is what a reviewer reads a diff against. */}
              {block.tag === VERBATIM_TAG
                ? <span className="truncate text-body font-semibold text-ink">{t('lifecycle.xml.verbatimBlock')}</span>
                : <code className="truncate text-body font-semibold text-ink">{`<${block.tag}>`}</code>}
              <Tag state={tagState[block.state]}>{t(`lifecycle.promptDetail.blockState.${block.state}`)}</Tag>
            </summary>
            <div className={sideBySide && block.before !== null && block.after !== null ? 'grid border-t border-border lg:grid-cols-2' : 'border-t border-border'}>
              {sideBySide && block.before !== null ? (
                <div className="max-h-96 overflow-auto border-b border-border bg-danger/5 p-4 lg:border-r lg:border-b-0">
                  {lines
                    ? <FilteredPane rows={lines.before} sharedWords={sharedWords} />
                    : sharedWords
                      ? <WordHeatmap text={block.before} sharedWords={sharedWords} className="text-caption" />
                      : <pre className="whitespace-pre-wrap font-mono text-caption text-ink">{block.before}</pre>}
                </div>
              ) : null}
              {/* No new side for a block that was removed. The old text is
                  already above it in the danger pane; repeating it on the right
                  is how a deletion ends up looking like something that stayed. */}
              {block.after !== null ? (
                <div className="max-h-96 overflow-auto bg-canvas p-4">
                  {lines
                    ? <FilteredPane rows={lines.after} sharedWords={sharedWords} />
                    : sharedWords
                      ? <WordHeatmap text={block.after} sharedWords={sharedWords} className="text-caption" />
                      : <pre className="whitespace-pre-wrap font-mono text-caption text-ink">{block.after}</pre>}
                </div>
              ) : null}
            </div>
          </details>
        );
      })}
    </div>
  );
}

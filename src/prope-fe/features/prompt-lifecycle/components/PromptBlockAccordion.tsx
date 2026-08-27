import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { WordHeatmap } from '@/features/prompt-lifecycle/components/WordHeatmap';
import { diffPromptBlocks } from '@/features/prompt-lifecycle/promptBlockDiff';
import { VERBATIM_TAG } from '@/features/prompt-lifecycle/xmlBlocks';
import { sharedWordsOf } from '@/features/prompt-lifecycle/wordOverlap';

interface PromptBlockAccordionProps {
  beforeBody?: string;
  body: string;
  onlyChanged?: boolean;
  sideBySide?: boolean;
}

const tagState = { added: 'success', changed: 'warning', unchanged: 'neutral', removed: 'danger' } as const;

export function PromptBlockAccordion({ beforeBody = '', body, onlyChanged = false, sideBySide = false }: PromptBlockAccordionProps) {
  const { t } = useTranslation();
  const blocks = diffPromptBlocks(beforeBody, body).filter((block) => !onlyChanged || block.state !== 'unchanged');
  const heatByBlockKey = useMemo(() => {
    const heat = new Map<string, Set<string>>();
    for (const block of blocks) {
      if (block.state === 'changed' && block.before !== null && block.after !== null) {
        heat.set(block.key, sharedWordsOf(block.before, block.after));
      }
    }
    return heat;
  }, [blocks]);
  return (
    <div className="grid gap-2">
      {blocks.map((block) => {
        const sharedWords = sideBySide ? heatByBlockKey.get(block.key) : undefined;
        return (
          <details key={block.key} open={block.state !== 'unchanged'} className="group overflow-hidden rounded-xl border border-border bg-surface">
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
                  {sharedWords
                    ? <WordHeatmap text={block.before} sharedWords={sharedWords} className="text-caption" />
                    : <pre className="whitespace-pre-wrap font-mono text-caption text-ink">{block.before}</pre>}
                </div>
              ) : null}
              <div className="max-h-96 overflow-auto bg-canvas p-4">
                {sharedWords && block.after !== null
                  ? <WordHeatmap text={block.after} sharedWords={sharedWords} className="text-caption" />
                  : <pre className="whitespace-pre-wrap font-mono text-caption text-ink">{block.after ?? block.before ?? ''}</pre>}
              </div>
            </div>
          </details>
        );
      })}
    </div>
  );
}

import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { diffPromptBlocks } from '@/features/prompt-lifecycle/promptBlockDiff';

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
  return (
    <div className="grid gap-2">
      {blocks.map((block) => (
        <details key={block.key} open={block.state !== 'unchanged'} className="group overflow-hidden rounded-xl border border-border bg-surface">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 focus-visible:outline-2 focus-visible:outline-focus">
            <code className="truncate text-body font-semibold text-ink">{`<${block.tag}>`}</code>
            <Tag state={tagState[block.state]}>{t(`lifecycle.promptDetail.blockState.${block.state}`)}</Tag>
          </summary>
          <div className={sideBySide && block.before !== null && block.after !== null ? 'grid border-t border-border lg:grid-cols-2' : 'border-t border-border'}>
            {sideBySide && block.before !== null ? (
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap border-b border-border bg-danger/5 p-4 text-caption text-ink lg:border-r lg:border-b-0">{block.before}</pre>
            ) : null}
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap bg-canvas p-4 text-caption text-ink">{block.after ?? block.before ?? ''}</pre>
          </div>
        </details>
      ))}
    </div>
  );
}

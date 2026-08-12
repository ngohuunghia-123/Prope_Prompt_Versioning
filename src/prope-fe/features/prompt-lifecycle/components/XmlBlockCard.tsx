import { ArrowDown, ArrowUp, Copy, Trash } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { extractTemplateTokens, type XmlBlock } from '@/features/prompt-lifecycle/xmlBlocks';

export interface XmlBlockCardProps {
  block: XmlBlock;
  first: boolean;
  last: boolean;
  onChange: (content: string) => void;
  onMove: (direction: -1 | 1) => void;
  onDuplicate: () => void;
  onRemove: () => void;
}

export function XmlBlockCard({ block, first, last, onChange, onMove, onDuplicate, onRemove }: XmlBlockCardProps) {
  const { t } = useTranslation();
  const tokens = extractTemplateTokens(block.content);
  return (
    <article className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-subtle px-4 py-3">
        <code className="font-semibold text-link">&lt;{block.tag}&gt;</code>
        <div className="flex items-center gap-1">
          <Button type="button" size="icon" intent="ghost" disabled={first} aria-label={t('lifecycle.xml.moveUp')} onClick={() => onMove(-1)}><ArrowUp aria-hidden /></Button>
          <Button type="button" size="icon" intent="ghost" disabled={last} aria-label={t('lifecycle.xml.moveDown')} onClick={() => onMove(1)}><ArrowDown aria-hidden /></Button>
          <Button type="button" size="icon" intent="ghost" aria-label={t('lifecycle.xml.duplicate')} onClick={onDuplicate}><Copy aria-hidden /></Button>
          <Button type="button" size="icon" intent="ghost" aria-label={t('lifecycle.xml.remove')} onClick={onRemove}><Trash aria-hidden /></Button>
        </div>
      </header>
      <div className="grid gap-3 p-4">
        <Textarea className="min-h-24 border-0 bg-transparent p-0 shadow-none focus:ring-0" label={t('lifecycle.xml.blockContent', { tag: block.tag })} value={block.content} onChange={(event) => onChange(event.target.value)} />
        {tokens.length ? <div className="flex flex-wrap items-center gap-2"><span className="text-caption text-muted">{t('lifecycle.xml.variables')}</span>{tokens.map((token) => <Tag key={token} state="neutral">{token}</Tag>)}</div> : null}
      </div>
    </article>
  );
}

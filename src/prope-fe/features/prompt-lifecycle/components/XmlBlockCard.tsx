import { ArrowDown, ArrowUp, Copy, Trash } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
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
  const [copiedToken, setCopiedToken] = useState<string>();
  const tokens = extractTemplateTokens(block.content);
  return (
    <article className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-subtle px-4 py-3">
        <code className="font-semibold text-link">&lt;{block.tag}&gt;</code>
        <div className="flex items-center gap-2">
          <button type="button" disabled={first} aria-label={t('lifecycle.xml.moveUp')} onClick={() => onMove(-1)} className="cursor-pointer text-muted hover:text-link disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-focus"><ArrowUp aria-hidden className="size-5" /></button>
          <button type="button" disabled={last} aria-label={t('lifecycle.xml.moveDown')} onClick={() => onMove(1)} className="cursor-pointer text-muted hover:text-link disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-focus"><ArrowDown aria-hidden className="size-5" /></button>
          <button type="button" aria-label={t('lifecycle.xml.duplicate')} onClick={onDuplicate} className="cursor-pointer text-muted hover:text-link focus-visible:outline-2 focus-visible:outline-focus"><Copy aria-hidden className="size-5" /></button>
          <button type="button" aria-label={t('lifecycle.xml.remove')} onClick={onRemove} className="cursor-pointer text-muted hover:text-danger-text focus-visible:outline-2 focus-visible:outline-focus"><Trash aria-hidden className="size-5" /></button>
        </div>
      </header>
      <div className="grid gap-3 p-4">
        <Textarea className="min-h-24 border-0 bg-transparent p-0 shadow-none focus:ring-0" label={t('lifecycle.xml.blockContent', { tag: block.tag })} value={block.content} onChange={(event) => onChange(event.target.value)} />
        {tokens.length ? <div className="flex flex-wrap items-center gap-2"><span className="text-caption text-muted">{t('lifecycle.xml.variables')}</span>{tokens.map((token) => <button key={token} type="button" onClick={() => { void navigator.clipboard.writeText(token); setCopiedToken(token); }} className="cursor-pointer focus-visible:outline-2 focus-visible:outline-focus"><Tag state="neutral">{copiedToken === token ? t('lifecycle.xml.variableCopied') : token}</Tag></button>)}</div> : null}
      </div>
    </article>
  );
}

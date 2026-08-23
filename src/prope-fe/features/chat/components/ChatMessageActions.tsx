import { Check, Copy, ThumbsDown, ThumbsUp, ArrowClockwise } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useChat } from '@/features/chat/ChatContext';
import type { ChatMessage } from '@/features/chat/types';
import { cn } from '@/lib/cn';

const reasons = ['incorrect', 'unsupported_source', 'misunderstood', 'other'] as const;

export function ChatMessageActions({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const { feedback, retry } = useChat();
  const [copied, setCopied] = useState(false);
  const [reasonsOpen, setReasonsOpen] = useState(false);

  const copy = () => {
    void navigator.clipboard?.writeText(message.text).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_500);
    });
  };

  return (
    <div className="mt-2 border-t border-border/60 pt-1.5">
      <div className="flex items-center gap-1">
        <button type="button" onClick={copy} aria-label={t('chat.actions.copy')} className="grid size-8 cursor-pointer place-items-center rounded-full text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus">{copied ? <Check aria-hidden className="size-3.5" /> : <Copy aria-hidden className="size-3.5" />}</button>
        <button type="button" onClick={() => retry(message.id)} aria-label={t('chat.actions.retry')} className="grid size-8 cursor-pointer place-items-center rounded-full text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"><ArrowClockwise aria-hidden className="size-3.5" /></button>
        <button type="button" aria-pressed={message.feedback === 'helpful'} onClick={() => feedback(message.id, 'helpful')} aria-label={t('chat.actions.helpful')} className={cn('grid size-8 cursor-pointer place-items-center rounded-full text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus', message.feedback === 'helpful' && 'bg-success text-success-text')}><ThumbsUp aria-hidden className="size-3.5" /></button>
        <button type="button" aria-pressed={message.feedback === 'not_helpful'} onClick={() => { feedback(message.id, 'not_helpful'); setReasonsOpen(true); }} aria-label={t('chat.actions.notHelpful')} className={cn('grid size-8 cursor-pointer place-items-center rounded-full text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus', message.feedback === 'not_helpful' && 'bg-warning text-warning-text')}><ThumbsDown aria-hidden className="size-3.5" /></button>
      </div>
      {reasonsOpen ? (
        <div className="mt-1.5 flex flex-wrap gap-1" role="group" aria-label={t('chat.feedback.reasonLabel')}>
          {reasons.map((reason) => <button key={reason} type="button" onClick={() => { feedback(message.id, 'not_helpful', reason); setReasonsOpen(false); }} className="cursor-pointer rounded-full border border-border bg-canvas px-2 py-1 text-overline text-muted hover:border-secondary hover:text-ink focus-visible:outline-2 focus-visible:outline-focus">{t(`chat.feedback.reason.${reason}`)}</button>)}
        </div>
      ) : null}
    </div>
  );
}

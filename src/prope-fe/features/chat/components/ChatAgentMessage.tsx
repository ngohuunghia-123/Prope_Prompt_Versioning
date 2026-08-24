import { BookOpenText, CaretDown, WarningCircle } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { ChatActivityTimeline } from '@/features/chat/components/ChatActivityTimeline';
import { ChatApprovalCard } from '@/features/chat/components/ChatApprovalCard';
import { ChatCitationPreview } from '@/features/chat/components/ChatCitationPreview';
import { ChatMarkdown } from '@/features/chat/components/ChatMarkdown';
import { ChatMessageActions } from '@/features/chat/components/ChatMessageActions';
import type { ChatMessage, Citation } from '@/features/chat/types';
import { cn } from '@/lib/cn';

export function ChatAgentMessage({ message, latest }: { message: ChatMessage; latest: boolean }) {
  const { t } = useTranslation();
  const { highlight } = useAgentSurface();
  const [source, setSource] = useState<Citation | null>(null);
  const ringCitations = latest && highlight === 'duplicate-card';
  const answer = message.text || (message.code ? t(`chat.refusal.${message.code}`, { defaultValue: t('chat.refusal.default') }) : '');
  const openCitation = (index: number) => setSource(message.citations?.find((citation) => citation.index === index) ?? null);

  return (
    <article className="grid min-w-0 max-w-[var(--prope-navigation-message-max-width)] animate-navigation-message gap-2 self-start overflow-hidden text-link">
      <ChatActivityTimeline activities={message.activities ?? []} trace={message.trace} streaming={message.streaming} />
      {answer ? (
        <div className="min-w-0 overflow-hidden rounded-navigation-panel bg-surface/70 px-2.5 py-2 shadow-inset">
          {message.degraded?.length ? (
            <div className="mb-2 flex items-start gap-1.5 rounded-navigation-panel bg-warning p-2 text-overline text-warning-text">
              <WarningCircle aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              <span>{message.degraded.map((reason) => t(`chat.degraded.${reason}`, { defaultValue: reason })).join(' · ')}</span>
            </div>
          ) : null}
          <ChatMarkdown onCitation={openCitation}>{answer}</ChatMarkdown>
          {message.citations?.length ? (
            <details className={cn('mt-2 rounded-navigation-panel transition-shadow', ringCitations && 'ring-2 ring-secondary')}>
              <summary className="flex cursor-pointer list-none items-center gap-1.5 py-1 text-overline font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus">
                <BookOpenText aria-hidden className="size-3.5" />{t('chat.sources.title', { count: message.citations.length })}<CaretDown aria-hidden className="ml-auto size-3.5" />
              </summary>
              <ol className="mt-1 grid gap-1">
                {message.citations.map((citation) => (
                  <li key={`${citation.kind}-${citation.reference}-${citation.index}`}>
                    <button type="button" onClick={() => setSource(citation)} className="flex w-full cursor-pointer items-start gap-2 rounded-navigation-panel bg-canvas px-2 py-1.5 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
                      <span className="grid size-5 shrink-0 place-items-center rounded-full bg-info text-overline font-semibold text-info-strong">{citation.index || '•'}</span>
                      <span className="min-w-0"><strong className="block truncate text-overline text-ink">{citation.label}</strong><span className="line-clamp-2 text-overline text-muted">{citation.excerpt}</span></span>
                    </button>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
          <ChatApprovalCard message={message} />
          {!message.streaming ? <ChatMessageActions message={message} /> : null}
        </div>
      ) : null}
      <ChatCitationPreview citation={source} onClose={() => setSource(null)} />
    </article>
  );
}

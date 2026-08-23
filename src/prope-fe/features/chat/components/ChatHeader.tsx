import { CaretDown, ClockCounterClockwise, Plus } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useChat } from '@/features/chat/ChatContext';
import { FLOATING_AGENT_ASSETS } from '@/features/floating-agent/assets';

export function ChatHeader() {
  const { t, i18n } = useTranslation();
  const { conversations, openConversation, startNewConversation } = useChat();
  const [historyOpen, setHistoryOpen] = useState(false);

  return (
    <header className="relative flex shrink-0 items-center gap-2 border-b border-border pb-2">
      <span className="size-8 shrink-0 overflow-hidden rounded-full bg-info"><img src={FLOATING_AGENT_ASSETS.avatar} alt="" className="size-full object-cover" /></span>
      <div className="min-w-0 flex-1"><h2 className="truncate text-caption font-semibold text-ink">PropAI</h2><p className="truncate text-overline text-muted">{t('chat.header.subtitle')}</p></div>
      {conversations.length ? (
        <details open={historyOpen} onToggle={(event) => setHistoryOpen(event.currentTarget.open)} className="relative">
          <summary aria-label={t('navigation.advanced.chat.history')} className="grid size-9 cursor-pointer list-none place-items-center rounded-full text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"><ClockCounterClockwise aria-hidden className="size-4" /><CaretDown aria-hidden className="absolute bottom-0 right-0 size-3" /></summary>
          <div className="absolute right-0 top-11 z-20 grid w-64 gap-1 rounded-navigation-panel border border-border bg-surface p-2 shadow-floating">
            <p className="px-2 py-1 text-overline font-semibold uppercase tracking-navigation-overline text-muted">{t('navigation.advanced.chat.history')}</p>
            {conversations.slice(0, 3).map((conversation) => (
              <button key={conversation.id} type="button" onClick={() => { openConversation(conversation.id); setHistoryOpen(false); }} className="grid cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-navigation-panel px-2 py-2 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
                <span className="truncate text-caption text-ink">{t(conversation.title_code, { defaultValue: t('chat.thread.general') })}</span>
                <time dateTime={conversation.updated_at} className="text-overline text-muted">{new Intl.DateTimeFormat(i18n.language, { day: '2-digit', month: '2-digit' }).format(new Date(conversation.updated_at))}</time>
              </button>
            ))}
          </div>
        </details>
      ) : null}
      <button type="button" onClick={startNewConversation} aria-label={t('chat.newThread')} title={t('chat.newThread')} className="grid size-9 cursor-pointer place-items-center rounded-full text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"><Plus aria-hidden className="size-4" /></button>
    </header>
  );
}

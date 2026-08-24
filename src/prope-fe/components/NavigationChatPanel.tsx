import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { ChatAgentMessage } from '@/features/chat/components/ChatAgentMessage';
import { ChatComposer } from '@/features/chat/components/ChatComposer';
import { ChatEmptyState } from '@/features/chat/components/ChatEmptyState';
import { ChatHeader } from '@/features/chat/components/ChatHeader';
import { ChatUserMessage } from '@/features/chat/components/ChatUserMessage';
import { useChat } from '@/features/chat/ChatContext';

export function NavigationChatPanel() {
  const { t } = useTranslation();
  const { error, messages, thinking } = useChat();
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages, thinking]);

  return (
    <section aria-label={t('navigation.advanced.chat.label')} className="flex h-full min-h-0 animate-navigation-panel flex-col gap-2.5">
      <ChatHeader />
      <div ref={threadRef} aria-live="polite" className="flex min-h-20 flex-1 flex-col gap-2.5 overflow-y-auto px-1 py-1 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
        {messages.length === 0 ? <ChatEmptyState /> : null}
        {messages.map((message, index) => message.role === 'user'
          ? <ChatUserMessage key={message.id} text={message.text} attachmentFormat={message.attachmentFormat} />
          : <ChatAgentMessage key={message.id} message={message} latest={index === messages.length - 1} />)}
        {error && !thinking ? <p role="alert" className="rounded-navigation-panel bg-danger px-2.5 py-2 text-caption text-danger-text">{t(`chat.refusal.${error}`, { defaultValue: t('chat.refusal.default') })}</p> : null}
      </div>
      <ChatComposer />
    </section>
  );
}

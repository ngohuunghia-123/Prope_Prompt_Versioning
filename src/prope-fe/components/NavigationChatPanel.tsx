import { PaperPlaneRight, Plus, Sparkle } from '@phosphor-icons/react';
import { useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { NavigationMessage } from '@/components/navigationTypes';
import { Button } from '@/components/ui/Button';

export interface NavigationChatPanelProps {
  input: string;
  messages: NavigationMessage[];
  thinking: boolean;
  onInputChange: (value: string) => void;
  onSend: () => void;
}

export function NavigationChatPanel({ input, messages, thinking, onInputChange, onSend }: NavigationChatPanelProps) {
  const { t } = useTranslation();
  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight; }, [messages]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSend();
    if (inputRef.current) inputRef.current.style.height = '';
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    onSend();
    event.currentTarget.style.height = '';
  };
  const history = [
    { id: 'release-evidence', time: 'now' },
    { id: 'prompt-access', time: 'fiveHoursAgo' },
    { id: 'regression-summary', time: 'twoDaysAgo' },
  ] as const;
  return (
    <section aria-label={t('navigation.advanced.chat.label')} className="flex h-full min-h-0 animate-navigation-panel flex-col gap-4">
      <div ref={threadRef} aria-live="polite" className="flex min-h-20 flex-1 flex-col gap-2.5 overflow-y-auto px-2.5 py-1 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
        {messages.length === 0 ? <div className="m-auto max-w-57.5 text-center text-caption text-muted"><Sparkle aria-hidden className="mx-auto mb-2 size-8 text-secondary" />{t('navigation.advanced.chat.empty')}</div> : null}
        {messages.map((message) => <div key={message.id} className={message.role === 'user' ? 'max-w-[var(--prope-navigation-message-max-width)] animate-navigation-message self-end rounded-navigation-panel bg-surface px-2.5 py-2 text-caption text-ink shadow-inset' : 'max-w-[var(--prope-navigation-message-max-width)] animate-navigation-message self-start rounded-navigation-panel bg-surface/55 px-2.5 py-2 text-caption text-link'}>{message.text}</div>)}
      </div>
      <div className="grid shrink-0 gap-2.5">
        <div aria-label={t('navigation.advanced.chat.historyLabel')} className="grid gap-2">
          <p className="m-0 text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t('navigation.advanced.chat.history')}</p>
          {history.map(({ id, time }) => <a key={id} href={`/app/chat/${id}`} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 text-caption text-link focus-visible:outline-2 focus-visible:outline-focus"><span className="truncate">{t(`navigation.advanced.chat.historyItems.${id}`)}</span><time className="text-overline font-bold tracking-navigation-time text-navigation-overline uppercase">{t(`navigation.advanced.relative.${time}`)}</time></a>)}
        </div>
        <form onSubmit={submit} className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-2 gap-y-1.5 rounded-navigation-panel bg-canvas p-2.5 shadow-inset [grid-template-areas:'input_input_input'_'attach_status_send']">
          <textarea ref={inputRef} data-navigation-chat-input rows={1} maxLength={500} value={input} aria-label={t('navigation.advanced.chat.inputLabel')} placeholder={t('navigation.advanced.chat.placeholder')} onKeyDown={handleKeyDown} onChange={(event) => { onInputChange(event.target.value); event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 96)}px`; }} className="min-h-5.5 max-h-24 w-full resize-none overflow-y-auto border-0 bg-transparent p-0 text-navigation-strong font-semibold text-ink outline-none placeholder:text-muted [grid-area:input]" />
          <Button type="button" intent="ghost" size="navigationIcon" aria-label={t('navigation.advanced.chat.attach')} title={t('navigation.advanced.chat.attach')} className="rounded-full [grid-area:attach]"><Plus aria-hidden /></Button>
          <span className="self-center text-right text-overline text-muted [grid-area:status]">{t(thinking ? 'navigation.advanced.chat.thinking' : 'navigation.advanced.chat.enterToSend')}</span>
          <Button type="submit" intent="ghost" size="navigationIcon" aria-label={t('navigation.advanced.chat.send')} title={t('navigation.advanced.chat.send')} className="rounded-full [grid-area:send]"><PaperPlaneRight aria-hidden /></Button>
        </form>
      </div>
    </section>
  );
}

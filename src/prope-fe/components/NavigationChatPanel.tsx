import { Check, PaperPlaneRight, Plus, Sparkle, X } from '@phosphor-icons/react';
import { useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { useChat } from '@/features/chat/ChatContext';
import type { ChatMessage } from '@/features/chat/types';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

/**
 * The assistant's surface.
 *
 * Three things here are Trust UX (deck 5, p59) rather than decoration, and each
 * one is the reason a row exists:
 *
 * * **the confirmation card** — the assistant never writes; it proposes, and
 *   this is where a person decides. It keeps rendering after the decision, with
 *   the buttons gone, because what was approved is the audit trail somebody
 *   came for.
 * * **the citation chips** — every factual claim resolves to a document section
 *   or a stored prompt, so *verify it yourself* is one click and not a leap.
 * * **the trace** — collapsed by default, because most turns do not need it, and
 *   present on every turn, because the one that does is the one where somebody
 *   is asking why the assistant did that.
 *
 * A degraded turn says so. An answer built with half the retrieval working must
 * not look identical to a healthy one.
 */

function TraceDetails({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  if (!message.trace?.length) return null;
  return (
    <details className="mt-1.5 text-overline text-muted">
      <summary className="cursor-pointer list-none text-overline uppercase tracking-navigation-overline focus-visible:outline-2 focus-visible:outline-focus">{t('chat.trace.label')}</summary>
      <ol className="mt-1 grid gap-0.5 pl-0">
        {message.trace.map((entry, index) => (
          <li key={`${entry.agent}-${index}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-2">
            <span className="truncate">{entry.agent} · {entry.action}{entry.status === 'ok' ? '' : ` · ${t(`chat.trace.status.${entry.status}`)}`}</span>
            <span className="tabular-nums">{entry.latency_ms}ms</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

function PendingCard({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const { decide, deciding } = useChat();
  const pending = message.pending;
  if (!pending) return null;

  const preview = Object.entries(pending.preview).filter(([, value]) => value !== null && value !== '');

  return (
    <div className="mt-2 grid gap-2 rounded-navigation-panel border border-border bg-canvas p-2.5 text-caption">
      <p className="m-0 text-overline font-bold uppercase tracking-navigation-overline text-navigation-overline">{t(`chat.pending.tool.${pending.tool}`)}</p>
      <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-0.5 text-overline text-muted">
        {preview.map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="truncate">{t(`chat.pending.field.${key}`, { defaultValue: key })}</dt>
            <dd className="m-0 truncate text-ink">{String(value)}</dd>
          </div>
        ))}
      </dl>
      {message.settled ? (
        <p className="m-0 text-overline text-muted">{t(`chat.pending.${message.settled}`)}</p>
      ) : (
        <div className="flex gap-2">
          <Button type="button" size="small" disabled={deciding} onClick={() => decide(pending.id, true)}><Check aria-hidden className="size-3.5" />{t('chat.pending.approve')}</Button>
          <Button type="button" intent="ghost" size="small" disabled={deciding} onClick={() => decide(pending.id, false)}><X aria-hidden className="size-3.5" />{t('chat.pending.reject')}</Button>
        </div>
      )}
      <p className="m-0 text-overline text-muted">{t('chat.pending.nothingSavedYet')}</p>
    </div>
  );
}

function AgentMessage({ message, latest }: { message: ChatMessage; latest: boolean }) {
  const { t } = useTranslation();
  const { highlight } = useAgentSurface();
  // A duplicate check answers *in the chat* — the near-matches are the citations
  // below, not a page somewhere else — so this is where the agent points.
  const ringCitations = latest && highlight === 'duplicate-card';
  return (
    <div className="max-w-[var(--prope-navigation-message-max-width)] animate-navigation-message self-start rounded-navigation-panel bg-surface/55 px-2.5 py-2 text-caption text-link">
      <p className="m-0 whitespace-pre-wrap">{message.text || (message.code ? t(`chat.refusal.${message.code}`, { defaultValue: t('chat.refusal.default') }) : '')}</p>
      {message.degraded?.length ? (
        <ul className="m-0 mt-1.5 flex list-none flex-wrap gap-1 p-0">
          {message.degraded.map((reason) => <li key={reason} className="rounded-full bg-surface px-1.5 py-0.5 text-overline text-muted">{t(`chat.degraded.${reason}`, { defaultValue: reason })}</li>)}
        </ul>
      ) : null}
      {message.citations?.length ? (
        <ul className={cn('m-0 mt-1.5 flex list-none flex-wrap gap-1 rounded-navigation-panel p-0 transition-shadow', ringCitations && 'p-1 ring-2 ring-secondary')}>
          {message.citations.map((citation) => (
            <li key={`${citation.kind}-${citation.reference}`}>
              {citation.kind === 'prompt'
                ? <a href={`/app/prompts/${citation.reference}`} className="rounded-full bg-surface px-1.5 py-0.5 text-overline text-link focus-visible:outline-2 focus-visible:outline-focus">{citation.label}</a>
                : <span className="rounded-full bg-surface px-1.5 py-0.5 text-overline text-muted">{citation.label}</span>}
            </li>
          ))}
        </ul>
      ) : null}
      <PendingCard message={message} />
      <TraceDetails message={message} />
    </div>
  );
}

export function NavigationChatPanel() {
  const { t } = useTranslation();
  const { attachment, setAttachment, conversations, error, input, messages, openConversation, send, setInput, startNewConversation, thinking } = useChat();
  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight; }, [messages, thinking]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    send();
    if (inputRef.current) inputRef.current.style.height = '';
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    send();
    event.currentTarget.style.height = '';
  };

  return (
    <section aria-label={t('navigation.advanced.chat.label')} className="flex h-full min-h-0 animate-navigation-panel flex-col gap-4">
      <div ref={threadRef} aria-live="polite" className="flex min-h-20 flex-1 flex-col gap-2.5 overflow-y-auto px-2.5 py-1 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
        {messages.length === 0 ? <div className="m-auto max-w-57.5 text-center text-caption text-muted"><Sparkle aria-hidden className="mx-auto mb-2 size-8 text-secondary" />{t('navigation.advanced.chat.empty')}</div> : null}
        {messages.map((message, index) => message.role === 'user'
          ? <div key={message.id} className="max-w-[var(--prope-navigation-message-max-width)] animate-navigation-message self-end rounded-navigation-panel bg-surface px-2.5 py-2 text-caption text-ink shadow-inset">{message.text}</div>
          : <AgentMessage key={message.id} message={message} latest={index === messages.length - 1} />)}
        {error ? <p role="alert" className="m-0 self-start text-caption text-danger">{t(`chat.refusal.${error}`, { defaultValue: t('chat.refusal.default') })}</p> : null}
      </div>
      <div className="grid shrink-0 gap-2.5">
        {conversations.length ? (
          <div aria-label={t('navigation.advanced.chat.historyLabel')} className="grid gap-2">
            <div className="flex items-center justify-between">
              <p className="m-0 text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t('navigation.advanced.chat.history')}</p>
              <button type="button" onClick={startNewConversation} className="border-0 bg-transparent p-0 text-overline text-link underline focus-visible:outline-2 focus-visible:outline-focus">{t('chat.newThread')}</button>
            </div>
            {conversations.slice(0, 3).map((conversation) => (
              <button key={conversation.id} type="button" onClick={() => openConversation(conversation.id)} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-0 bg-transparent p-0 text-left text-caption text-link focus-visible:outline-2 focus-visible:outline-focus">
                <span className="truncate">{t(conversation.title_code, { defaultValue: t('chat.thread.general') })}</span>
                <time dateTime={conversation.updated_at} className="text-overline font-bold tracking-navigation-time text-navigation-overline uppercase">{new Date(conversation.updated_at).toLocaleDateString()}</time>
              </button>
            ))}
          </div>
        ) : null}
        {attachment ? (
          <div className="grid gap-1 rounded-navigation-panel bg-canvas p-2.5 text-overline text-muted shadow-inset">
            <div className="flex items-center justify-between gap-2">
              <span>{t('chat.attachment.attached', { count: attachment.length })}</span>
              <button type="button" onClick={() => setAttachment('')} className="border-0 bg-transparent p-0 text-overline text-link underline focus-visible:outline-2 focus-visible:outline-focus">{t('chat.attachment.remove')}</button>
            </div>
            <p className="m-0 truncate text-ink">{attachment.slice(0, 80)}</p>
          </div>
        ) : null}
        <form onSubmit={submit} className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-2 gap-y-1.5 rounded-navigation-panel bg-canvas p-2.5 shadow-inset [grid-template-areas:'input_input_input'_'attach_status_send']">
          <textarea ref={inputRef} data-navigation-chat-input rows={1} maxLength={4000} value={input} aria-label={t('navigation.advanced.chat.inputLabel')} placeholder={t('navigation.advanced.chat.placeholder')} onKeyDown={handleKeyDown} onChange={(event) => { setInput(event.target.value); event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 96)}px`; }} className="min-h-5.5 max-h-24 w-full resize-none overflow-y-auto border-0 bg-transparent p-0 text-navigation-strong font-semibold text-ink outline-none placeholder:text-muted [grid-area:input]" />
          {/* Paste, not upload: the attachment is a prompt the person already has
              in their clipboard, and a file picker here would be a second import
              path with none of the format handling the import screen owns. */}
          <Button type="button" intent="ghost" size="navigationIcon" aria-label={t('navigation.advanced.chat.attach')} title={t('navigation.advanced.chat.attach')} onClick={() => { void navigator.clipboard?.readText().then((text) => setAttachment(text.trim())).catch(() => undefined); }} className="rounded-full [grid-area:attach]"><Plus aria-hidden /></Button>
          <span className="self-center text-right text-overline text-muted [grid-area:status]">{t(thinking ? 'navigation.advanced.chat.thinking' : 'navigation.advanced.chat.enterToSend')}</span>
          <Button type="submit" intent="ghost" size="navigationIcon" disabled={thinking} aria-label={t('navigation.advanced.chat.send')} title={t('navigation.advanced.chat.send')} className="rounded-full [grid-area:send]"><PaperPlaneRight aria-hidden /></Button>
        </form>
      </div>
    </section>
  );
}

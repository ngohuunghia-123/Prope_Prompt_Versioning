import { ArrowRight, Check, Copy, X } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useChat } from '@/features/chat/ChatContext';
import type { ChatMessage } from '@/features/chat/types';

// Only these tools offer editable identity on the card; everything else stays
// read-only. Mirrors the backend whitelist exactly - a field edited here that
// the server does not accept answers 422 and its code renders as an honest
// refusal instead of the generic failure.
const EDITABLE_TOOLS = new Set(['create_prompt']);

export function ChatApprovalCard({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const { decide, deciding } = useChat();
  const pending = message.pending;
  const [titleDraft, setTitleDraft] = useState<string | null>(null);
  const [nameDraft, setNameDraft] = useState<string | null>(null);
  if (!pending) return null;
  const editable = !message.settled && EDITABLE_TOOLS.has(pending.tool);
  const preview = Object.entries(pending.preview).filter(([, value]) => value !== null && value !== '');
  const titleValue = titleDraft ?? String(pending.preview.title ?? '');
  const nameValue = nameDraft ?? String(pending.preview.name ?? '');
  const edits: Record<string, string> = {};
  if (titleValue !== String(pending.preview.title ?? '')) edits.title = titleValue;
  if (nameValue !== String(pending.preview.name ?? '')) edits.name = nameValue;

  return (
    <section className="mt-2 grid min-w-0 max-w-full gap-2 overflow-hidden rounded-navigation-panel border border-border bg-canvas p-2.5 text-caption" aria-label={t(`chat.pending.tool.${pending.tool}`)}>
      <div className="min-w-0">
        <p className="text-overline font-bold uppercase tracking-navigation-overline text-navigation-overline">{t(`chat.pending.tool.${pending.tool}`)}</p>
        <p className="mt-1 break-words text-caption font-semibold text-ink [overflow-wrap:anywhere]">{pending.summary}</p>
      </div>
      {editable ? (
        <div className="grid gap-2">
          <Input label={t('chat.pending.field.title', { defaultValue: 'title' })} value={titleValue} maxLength={200} onChange={(event) => setTitleDraft(event.target.value)} className="text-caption" />
          <Input label={t('chat.pending.field.name', { defaultValue: 'name' })} value={nameValue} maxLength={100} hint={t('chat.pending.editableHint')} onChange={(event) => setNameDraft(event.target.value)} className="text-caption" />
        </div>
      ) : (
        <dl className="grid min-w-0 grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-2 gap-y-1 text-overline text-muted">
          {preview.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="min-w-0 truncate">{t(`chat.pending.field.${key}`, { defaultValue: key })}</dt>
              <dd className="min-w-0 break-words text-ink [overflow-wrap:anywhere]">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {message.settled ? (
        <div className="grid gap-2">
          <p className="text-overline text-muted">{t(`chat.pending.${message.settled}`)}</p>
          <SecretOnce secret={message.actionResult?.secret ?? null} />
          {message.actionResult?.promptId ? <a href={`/app/prompts/${message.actionResult.promptId}`} className="flex cursor-pointer items-center gap-1 text-overline text-link underline">{t('chat.pending.openResult')}<ArrowRight aria-hidden className="size-3.5" /></a> : null}
        </div>
      ) : (
        <div className="flex gap-2">
          <Button type="button" size="small" loading={deciding} onClick={() => decide(pending.id, true, edits)}><Check aria-hidden className="size-3.5" />{t('chat.pending.approve')}</Button>
          <Button type="button" intent="ghost" size="small" disabled={deciding} onClick={() => decide(pending.id, false)}><X aria-hidden className="size-3.5" />{t('chat.pending.reject')}</Button>
        </div>
      )}
      {!message.settled ? <p className="text-overline text-muted">{t('chat.pending.nothingSavedYet')}</p> : null}
    </section>
  );
}

/**
 * A minted key's plaintext, shown once. The server sends it on the decision
 * response and nowhere else — it never re-fetches — so this is the only place
 * it can ever be copied from.
 */
function SecretOnce({ secret }: { secret: string | null }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  if (!secret) return null;
  const copy = () => {
    void navigator.clipboard.writeText(secret).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2_000);
    });
  };
  return (
    <div className="grid gap-1 rounded-navigation-panel border border-border bg-canvas p-2">
      <p className="text-overline font-bold uppercase tracking-navigation-overline text-navigation-overline">{t('chat.pending.keyReady')}</p>
      <div className="flex items-center justify-between gap-2">
        <code className="truncate text-caption text-ink" aria-label={t('chat.pending.keyReady')}>{secret}</code>
        <Button type="button" intent="ghost" size="small" onClick={copy} aria-label={t(copied ? 'chat.pending.copied' : 'chat.pending.copy')}>
          <Copy aria-hidden className="size-3.5" />{t(copied ? 'chat.pending.copied' : 'chat.pending.copy')}
        </Button>
      </div>
    </div>
  );
}

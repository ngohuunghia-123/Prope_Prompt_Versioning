import { ArrowRight, Check, X } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { useChat } from '@/features/chat/ChatContext';
import type { ChatMessage } from '@/features/chat/types';

export function ChatApprovalCard({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const { decide, deciding } = useChat();
  const pending = message.pending;
  if (!pending) return null;
  const preview = Object.entries(pending.preview).filter(([, value]) => value !== null && value !== '');

  return (
    <section className="mt-2 grid gap-2 rounded-navigation-panel border border-border bg-canvas p-2.5 text-caption" aria-label={t(`chat.pending.tool.${pending.tool}`)}>
      <div>
        <p className="text-overline font-bold uppercase tracking-navigation-overline text-navigation-overline">{t(`chat.pending.tool.${pending.tool}`)}</p>
        <p className="mt-1 text-caption font-semibold text-ink">{pending.summary}</p>
      </div>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 text-overline text-muted">
        {preview.map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="truncate">{t(`chat.pending.field.${key}`, { defaultValue: key })}</dt>
            <dd className="truncate text-ink">{String(value)}</dd>
          </div>
        ))}
      </dl>
      {message.settled ? (
        <div className="grid gap-2">
          <p className="text-overline text-muted">{t(`chat.pending.${message.settled}`)}</p>
          {message.actionResult?.promptId ? <a href={`/app/prompts/${message.actionResult.promptId}`} className="flex cursor-pointer items-center gap-1 text-overline text-link underline">{t('chat.pending.openResult')}<ArrowRight aria-hidden className="size-3.5" /></a> : null}
        </div>
      ) : (
        <div className="flex gap-2">
          <Button type="button" size="small" loading={deciding} onClick={() => decide(pending.id, true)}><Check aria-hidden className="size-3.5" />{t('chat.pending.approve')}</Button>
          <Button type="button" intent="ghost" size="small" disabled={deciding} onClick={() => decide(pending.id, false)}><X aria-hidden className="size-3.5" />{t('chat.pending.reject')}</Button>
        </div>
      )}
      {!message.settled ? <p className="text-overline text-muted">{t('chat.pending.nothingSavedYet')}</p> : null}
    </section>
  );
}

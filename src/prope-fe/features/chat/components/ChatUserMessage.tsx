import { Paperclip } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { ChatMarkdown } from '@/features/chat/components/ChatMarkdown';
import type { AttachmentFormat } from '@/features/chat/types';

/**
 * One of the person's turns. The body of an attached file never enters the
 * transcript — only the fact that one rode along, as its format — so the chip
 * is the honest thing to render: what was sent, not a fake preview of it.
 */
export function ChatUserMessage({ text, attachmentFormat }: { text: string; attachmentFormat?: AttachmentFormat | null }) {
  const { t } = useTranslation();
  return (
    <div className="max-w-[var(--prope-navigation-message-max-width)] animate-navigation-message self-end rounded-navigation-panel bg-surface px-2.5 py-2 text-ink shadow-inset">
      {attachmentFormat ? (
        <p className="mb-1 flex items-center gap-1 text-overline text-muted">
          <Paperclip aria-hidden className="size-3 shrink-0" />
          <span>{t('chat.attachment.attachedFile')} · {attachmentFormat.toUpperCase()}</span>
        </p>
      ) : null}
      {text ? <ChatMarkdown>{text}</ChatMarkdown> : null}
    </div>
  );
}

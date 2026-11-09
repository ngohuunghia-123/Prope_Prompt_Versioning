import { useTranslation } from 'react-i18next';
import { useChat } from '@/features/chat/ChatContext';
import { ChatHeader } from '@/features/chat/components/ChatHeader';
import { ChatComposer } from '@/features/chat/components/ChatComposer';
import { ChatUserMessage } from '@/features/chat/components/ChatUserMessage';
import { ChatAgentMessage } from '@/features/chat/components/ChatAgentMessage';
import { SavedRevisionTools } from '@/features/connectors/SavedRevisionTools';
import type { SessionSnapshot } from '@/features/connectors/sessionChatContracts';

export function SessionChatContent({ snapshot }: { snapshot: SessionSnapshot }) {
  const { t } = useTranslation(); const chat = useChat();
  const sendDisabledReason = snapshot.uncertain ? t('connector.sessionUncertain')
    : !snapshot.has_content ? t('connector.sessionEmpty') : undefined;
  return <div className="space-y-3">
    <ChatHeader />
    {!chat.messages.length ? <p className="text-body text-muted">{t('connector.sessionChatEmpty')}</p> : null}
    <fieldset disabled={snapshot.uncertain} className="grid max-h-96 min-w-0 gap-3 overflow-y-auto" aria-live="polite">{chat.messages.map((message, index) => message.role === 'user'
      ? <ChatUserMessage key={message.id} text={message.text} attachmentFormat={message.attachmentFormat} />
      : <ChatAgentMessage key={message.id} message={message} latest={index === chat.messages.length - 1} />)}</fieldset>
    {chat.error ? <p role="alert" className="rounded-lg bg-danger p-3 text-danger-text">{t('connector.sessionChatError', { code: chat.error })}</p> : null}
    <ChatComposer allowAttachments={false} allowVoice={false} requireText sendDisabledReason={sendDisabledReason} />
    {chat.messages.filter((message) => message.actionResult?.promptId && message.actionResult.versionId).map((message) => <details key={message.id} className="rounded-lg border border-border p-3">
      <summary className="cursor-pointer">{t('connector.sessionOpenResult')}</summary><SavedRevisionTools result={{ prompt_id: message.actionResult?.promptId, version_id: message.actionResult?.versionId }} />
    </details>)}
  </div>;
}

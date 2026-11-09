import { useTranslation } from 'react-i18next';
import type { ConversationObservation } from '@/features/connectors/contracts';
import { ConversationIdentityCard } from '@/features/connectors/ConversationIdentityCard';

export function ConnectionConversations({ connectionId, conversations, limited, canReadTitle }: { connectionId: string; conversations: ConversationObservation[]; limited: boolean; canReadTitle: boolean }) {
  const { t } = useTranslation();
  return <section className="space-y-2">
    <h4 className="text-caption font-semibold text-muted">{t('connector.connectionConversations')}</h4>
    {conversations.length === 0 ? <p role="status">{t('connector.conversationUnknown')}</p> : null}
    <ul className="space-y-2">{conversations.map((conversation) => <ConversationIdentityCard key={conversation.thread_id} connectionId={connectionId} conversation={conversation} canReadTitle={canReadTitle} />)}</ul>
    {limited ? <p>{t('connector.conversationHistoryLimited')}</p> : null}
  </section>;
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { getConversationTitle } from '@/features/connectors/api';
import type { ConversationObservation } from '@/features/connectors/contracts';
import { grantSessionChat } from '@/features/connectors/sessionChatApi';

export function ConversationIdentityCard({ connectionId, conversation, canReadTitle }: { connectionId: string; conversation: ConversationObservation; canReadTitle: boolean }) {
  const { t, i18n } = useTranslation(); const client = useQueryClient();
  const grant = useMutation({ mutationFn: async () => {
    const snapshot = await grantSessionChat(connectionId, conversation.thread_id);
    client.setQueryData(['connector', 'session-chat'], snapshot);
  } });
  const name = useQuery({ queryKey: ['connector', 'conversation-title', connectionId, conversation.thread_id],
    queryFn: () => getConversationTitle(connectionId, conversation.thread_id), enabled: canReadTitle, retry: false, staleTime: 60_000 });
  const formatter = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'medium' });
  return <li className="space-y-2 rounded-lg border border-border p-3">
    <h5 className="truncate text-body font-semibold" title={name.data?.title ?? undefined}>{name.data?.title ?? t(name.isFetching ? 'common.loading' : name.isSuccess ? 'connector.conversationNoTitleReturned' : 'connector.conversationTitleNotLoaded')}</h5>
    <code className="block select-all break-all font-mono text-caption">{conversation.thread_id}</code>
    <p className="text-caption text-muted">{t(conversation.source === 'mcp_metadata_thread_id' ? 'connector.conversationObserved' : 'connector.conversationSelected')}</p>
    <ConnectorError error={name.error} />
    <Button intent="neutral" size="small" loading={grant.isPending} disabled={!canReadTitle} onClick={() => grant.mutate()}>{t('connector.openSessionChat')}</Button>
    <ConnectorError error={grant.error} />
    <details className="text-caption text-muted"><summary className="cursor-pointer focus-visible:outline focus-visible:outline-focus">{t('connector.conversationDetails')}</summary>
      <div className="mt-2 space-y-2"><p>{t('connector.conversationTitleSource')}</p>
        <p>{t('connector.conversationLastSeen', { time: formatter.format(conversation.last_seen) })}</p>
        {name.data ? <p>{t('connector.conversationTitleCheckedAt', { time: formatter.format(name.data.checked_at) })}</p> : null}
        <Button intent="neutral" size="small" loading={name.isFetching} disabled={!canReadTitle || name.isFetching} onClick={() => void name.refetch()}>{t('connector.refreshConversationTitle')}</Button>
      </div>
    </details>
    {!canReadTitle ? <p className="text-caption text-muted">{t('connector.conversationTitleRequiresCodex')}</p> : null}
  </li>;
}

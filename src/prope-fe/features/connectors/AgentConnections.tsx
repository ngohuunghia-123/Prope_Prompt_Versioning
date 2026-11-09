import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { checkAgentConnection, chooseConversation, getAgentConnections } from '@/features/connectors/api';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { ApiError } from '@/lib/apiClient';
import { ConnectionConversations } from '@/features/connectors/ConnectionConversations';

export function AgentConnections() {
  const { t } = useTranslation(); const client = useQueryClient();
  const connections = useQuery({ queryKey: ['connector', 'agents'], queryFn: getAgentConnections, refetchInterval: 5000 });
  const check = useMutation({ mutationFn: checkAgentConnection, onSuccess: () => client.invalidateQueries({ queryKey: ['connector', 'agents'] }) });
  const choose = useMutation({ mutationFn: chooseConversation, onSuccess: () => client.invalidateQueries({ queryKey: ['connector', 'agents'] }) });
  return <section className="mt-3 space-y-3">
    <h2 className="font-display text-heading-3">{t('connector.agentConnections')}</h2>
    <ConnectorError error={connections.error ?? check.error ?? choose.error} />
    {check.error instanceof ApiError && check.error.code === 'heartbeat_timeout' ? <p role="alert">{t('connector.agentCheckTimeout')}</p> : null}
    {connections.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {connections.data?.length === 0 ? <p>{t('connector.noAgentConnections')}</p> : null}
    <ul className="space-y-3">{(connections.data ?? []).map((connection) => <li key={connection.connection_id} className="space-y-2 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1"><h3 className="font-semibold">{connection.client_name === 'codex-mcp-client' ? t('connector.codexClientName') : connection.client_name ?? t('connector.unknownAgent')}</h3>
        <code className="text-caption text-muted">{connection.connection_id}</code><span role="status" className="text-caption text-muted">{t(`connector.agentStatus.${connection.status}`)}</span>
        {connection.namespace ? <span className="text-caption text-muted">{connection.namespace}</span> : null}</div>
      <div className="flex flex-wrap gap-2">
        {connection.client_name === 'codex-mcp-client' ? <Button intent="neutral" size="small" loading={choose.isPending && choose.variables === connection.connection_id} disabled={connection.status === 'pending' || choose.isPending} onClick={() => choose.mutate(connection.connection_id)}>{t('connector.chooseCodexConversation')}</Button> : null}
        <Button intent="neutral" size="small" loading={check.isPending && check.variables === connection.connection_id} disabled={connection.status === 'pending' || check.isPending}
          onClick={() => check.mutate(connection.connection_id)}>{t('connector.checkAgent')}</Button>
      </div>
      <ConnectionConversations connectionId={connection.connection_id} conversations={connection.conversations} limited={connection.conversation_history_limited} canReadTitle={connection.status !== 'pending' && connection.client_name === 'codex-mcp-client'} />
      {check.isPending && check.variables === connection.connection_id ? <p role="status">{t('connector.agentChecking')}</p> : null}
      {check.isSuccess && check.data.connection_id === connection.connection_id && connection.status === 'connected' ? <p role="status" className="text-success-text">{t('connector.agentCheckPassed')}</p> : null}
      <details className="text-caption text-muted"><summary className="cursor-pointer focus-visible:outline focus-visible:outline-focus">{t('connector.connectionDetails')}</summary>
        <div className="mt-2 space-y-2"><p>{t('connector.agentCheckHint')}</p><p>{t('connector.conversationIdentityHint')}</p><p>{t('connector.conversationScopeHint')}</p></div>
      </details>
    </li>)}</ul>
  </section>;
}

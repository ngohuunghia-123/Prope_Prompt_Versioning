import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { getConnectorState } from '@/features/connectors/api';
import { callHost } from '@/features/connectors/bridge';
import { CaptureCard } from '@/features/connectors/CaptureCard';
import { EvaluationCard } from '@/features/connectors/EvaluationCard';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { DirectWorkspace } from '@/features/connectors/DirectWorkspace';
import { AgentConnections } from '@/features/connectors/AgentConnections';
import { SessionChatPanel } from '@/features/connectors/SessionChatPanel';

export function ConnectorPanel() {
  const { t } = useTranslation(); const client = useQueryClient();
  const [agentsOpen, setAgentsOpen] = useState(false);
  const state = useQuery({ queryKey: ['connector', 'state'], queryFn: getConnectorState, refetchInterval: 30_000 });
  const command = useMutation({ mutationFn: (action: string) => callHost(action), onSuccess: () => client.invalidateQueries({ queryKey: ['connector'] }) });
  return <main className="min-h-screen space-y-4 bg-canvas p-4 text-ink">
    <h1 className="font-display text-heading-2">{t('connector.title')}</h1>
    <p className="text-body text-muted">{t('connector.scope')}</p>
    <nav className="flex flex-wrap gap-2" aria-label={t('connector.actions')}>
      {['connect', 'disconnect'].map((action) => <Button key={action} intent="secondary" disabled={command.isPending} onClick={() => command.mutate(action)}>{t(`connector.${action}`)}</Button>)}
      <Button intent="secondary" onClick={() => void client.invalidateQueries()}>{t('connector.refreshData')}</Button>
    </nav>
    <ConnectorError error={command.error ?? state.error} />
    {state.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {state.data ? <>
      <p>{state.data.connected ? t('connector.workspace', { name: state.data.workspace_name }) : t('connector.disconnected')}</p>
      {state.data.connected ? <SessionChatPanel key={`chat:${state.data.workspace_id}`} /> : null}
      {state.data.connected ? <fieldset disabled={command.isPending}><DirectWorkspace key={state.data.workspace_id} /></fieldset> : null}
      <details onToggle={(event) => setAgentsOpen(event.currentTarget.open)} className="rounded-lg border border-border p-3"><summary className="cursor-pointer focus-visible:outline focus-visible:outline-focus">{t('connector.optionalAgent')}</summary>
        <p className="mt-3 text-body text-muted">{t('connector.pairWithoutChat')}</p>
        <div className="mt-3 flex flex-wrap gap-2">{['pair', 'configuration'].map((action) => <Button key={action} intent="secondary" disabled={command.isPending} onClick={() => command.mutate(action)}>{t(`connector.${action}`)}</Button>)}</div>
        {state.data.connected && agentsOpen ? <fieldset disabled={command.isPending}><AgentConnections key={state.data.workspace_id} /></fieldset> : null}
      </details>
      {state.data.proposals.length === 0 ? <p role="status" className="rounded-lg border border-border p-4 text-muted">{t('connector.empty')}</p> : null}
      {state.data.proposals.map((proposal) => proposal.input.kind === 'evaluation'
        ? <EvaluationCard key={proposal.id} proposal={proposal} />
        : <CaptureCard key={proposal.id} proposal={proposal} />)}
    </> : null}
  </main>;
}

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { ChatProvider } from '@/features/chat/ChatProvider';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { getSessionChat, refreshSessionChat, revokeSessionChat, sessionChatTransport } from '@/features/connectors/sessionChatApi';
import { SessionChatContent } from '@/features/connectors/SessionChatContent';
import { OpenRevisionForm } from '@/features/connectors/OpenRevisionForm';
import { RevisionWorkspace } from '@/features/connectors/RevisionWorkspace';

export function SessionChatPanel() {
  const { t, i18n } = useTranslation(); const client = useQueryClient();
  const [opened, setOpened] = useState<{ grantId: string; promptId: string; versionId: string } | null>(null);
  const [openingPrompt, setOpeningPrompt] = useState<{ grantId: string; promptId: string } | null>(null);
  const state = useQuery({ queryKey: ['connector', 'session-chat'], queryFn: getSessionChat, refetchInterval: 5000, retry: false });
  const snapshot = state.data;
  const openPrompt = (promptId: string) => { if (snapshot) { setOpeningPrompt({ grantId: snapshot.grant_id, promptId }); setOpened(null); } };
  const refresh = useMutation({ mutationFn: async (grantId: string) => {
    const snapshot = await refreshSessionChat(grantId);
    client.setQueryData(['connector', 'session-chat'], snapshot);
  } });
  const revoke = useMutation({ mutationFn: revokeSessionChat, onSuccess: () => client.setQueryData(['connector', 'session-chat'], null) });
  const transport = useMemo(() => snapshot ? sessionChatTransport(snapshot, () => client.invalidateQueries({ queryKey: ['connector', 'session-chat'] })) : undefined, [snapshot, client]);
  return <section className="space-y-3 rounded-lg border border-border bg-surface p-4" aria-label={t('connector.sessionChatTitle')}>
    <h2 className="font-display text-heading-3">{t('connector.sessionChatTitle')}</h2>
    <ConnectorError error={state.error ?? refresh.error ?? revoke.error} />
    {state.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {!state.isPending && !snapshot ? <p>{t('connector.sessionGrantHint')}</p> : null}
    {snapshot && transport ? <div key={snapshot.grant_id} className="space-y-3">
      <h3 className="break-words font-semibold">{snapshot.title ?? t('connector.conversationNoTitleReturned')}</h3>
      <p className="text-caption text-muted">{t('connector.sessionSnapshotTime', { time: new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'medium' }).format(snapshot.read_at) })}</p>
      <details className="text-caption text-muted"><summary className="cursor-pointer">{t('connector.sessionReadDetails')}</summary>
        <code className="my-2 block break-all font-mono">{snapshot.thread_id}</code><p>{t('connector.sessionDisclosure')}</p></details>
      <div className="flex flex-wrap gap-2"><Button intent="neutral" loading={refresh.isPending} disabled={revoke.isPending} onClick={() => refresh.mutate(snapshot.grant_id)}>{t('connector.sessionRefresh')}</Button>
        <Button intent="neutral" loading={revoke.isPending} onClick={() => revoke.mutate(snapshot.grant_id)}>{t('connector.sessionRevoke')}</Button></div>
      <fieldset disabled={refresh.isPending || revoke.isPending}><MemoryRouter><ChatProvider key={snapshot.grant_id} transport={transport} embedded openPrompt={openPrompt}><SessionChatContent snapshot={snapshot} /></ChatProvider></MemoryRouter></fieldset>
      {openingPrompt?.grantId === snapshot.grant_id ? <OpenRevisionForm key={openingPrompt.promptId} initialPromptId={openingPrompt.promptId} onOpen={(target) => { setOpened({ grantId: snapshot.grant_id, promptId: target.prompt_id, versionId: target.version_id }); setOpeningPrompt(null); }} /> : null}
      {opened?.grantId === snapshot.grant_id ? <RevisionWorkspace promptId={opened.promptId} versionId={opened.versionId} /> : null}
    </div> : null}
  </section>;
}

import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { getPrompts, getRevision, getRevisions } from '@/features/connectors/api';
import { callHost } from '@/features/connectors/bridge';
import type { Pending } from '@/features/connectors/contracts';
import { DestinationForm } from '@/features/connectors/DestinationForm';
import { SavedRevisionTools } from '@/features/connectors/SavedRevisionTools';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { PANEL_OWNER } from '@/features/connectors/directContracts';

export function CaptureCard({ proposal }: { proposal: Pending }) {
  const { t } = useTranslation();
  const input = proposal.input;
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (proposal.status === 'pending') heading.current?.scrollIntoView({ block: 'start' }); }, [proposal.status]);
  const [promptId, setPromptId] = useState(input.kind === 'revision' ? input.prompt_id : '');
  const [baseId, setBaseId] = useState(input.kind === 'revision' ? input.base_version_id : '');
  const prompts = useQuery({ queryKey: ['connector', 'prompts'], queryFn: getPrompts });
  const revisions = useQuery({ queryKey: ['connector', 'revisions', promptId], queryFn: () => getRevisions(promptId), enabled: Boolean(promptId) });
  const base = useQuery({ queryKey: ['connector', 'revision', baseId], queryFn: () => getRevision(baseId), enabled: Boolean(baseId) });
  const reject = useMutation({ mutationFn: () => callHost('reject', { proposal_id: proposal.id }) });
  if (input.kind === 'evaluation') return null;
  const available = prompts.data?.filter((prompt) => prompt.namespace === proposal.namespace) ?? [];
  return <article className="space-y-4 rounded-lg border border-border bg-surface p-4">
    <h2 ref={heading} className="font-display text-heading-3">{input.kind === 'revision' ? t('connector.candidateProposal') : proposal.connection_id === PANEL_OWNER ? t('connector.manualTitle') : t('connector.captureTitle', { host: input.host })}</h2>
    <p className="text-caption text-muted">{t(proposal.connection_id === PANEL_OWNER ? 'connector.directHint' : 'connector.sourceDisclaimer')}</p>
    <Textarea label={t('connector.original')} value={input.source} readOnly />
    <ConnectorError error={prompts.error ?? revisions.error ?? base.error ?? reject.error} />
    {proposal.status === 'saved' ? <><p role="status">{t('connector.saved')}</p><SavedRevisionTools result={proposal.result} /></> : null}
    {proposal.status === 'uncertain' ? <><p role="alert">{t('connector.uncertain')}</p><pre className="whitespace-pre-wrap break-all text-caption">{JSON.stringify(proposal.result, null, 2)}</pre></> : null}
    {proposal.status === 'pending' ? <>
      {prompts.isPending ? <p role="status">{t('common.loading')}</p> : <Select label={t('connector.target')} value={promptId} disabled={input.kind === 'revision'}
        options={[{ value: '', label: t('connector.createNew') }, ...available.map((prompt) => ({ value: prompt.prompt_id, label: prompt.model_name }))]}
        onValueChange={(value) => { setPromptId(value); setBaseId(''); }} />}
      {promptId ? <Select label={t('connector.base')} value={baseId} disabled={input.kind === 'revision'} onValueChange={setBaseId}
        options={[{ value: '', label: t('connector.choose') }, ...(revisions.data ?? []).map((revision) => ({ value: revision.version_id, label: t('connector.revision', { number: revision.revision_number }) }))]} /> : null}
      {promptId && revisions.data?.length !== 0 && (base.isPending || base.isFetching || !baseId) ? <p role="status">{t(baseId ? 'common.loading' : 'connector.chooseBase')}</p> : null}
      {!prompts.isPending && (!promptId || (base.data && !base.isFetching && !base.isError) || revisions.data?.length === 0) ? <DestinationForm key={`${promptId}:${baseId}:${JSON.stringify(base.data ?? null)}`} proposal={proposal} promptId={promptId} base={base.data} /> : null}
    </> : null}
    <Button intent="secondary" loading={reject.isPending} onClick={() => reject.mutate()}>{t('connector.dismiss')}</Button>
  </article>;
}

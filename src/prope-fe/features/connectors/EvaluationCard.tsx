import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import type { Pending } from '@/features/connectors/contracts';
import { getRevision, pairSchema } from '@/features/connectors/api';
import { callHost } from '@/features/connectors/bridge';
import { ComparisonResults } from '@/features/connectors/ComparisonResults';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function EvaluationCard({ proposal }: { proposal: Pending }) {
  const { t } = useTranslation(); const input = proposal.input;
  const originalId = input.kind === 'evaluation' ? input.original_version_id : '';
  const candidateId = input.kind === 'evaluation' ? input.candidate_version_id : '';
  const original = useQuery({ queryKey: ['connector', 'revision', originalId], queryFn: () => getRevision(originalId), enabled: Boolean(originalId) });
  const candidate = useQuery({ queryKey: ['connector', 'revision', candidateId], queryFn: () => getRevision(candidateId), enabled: Boolean(candidateId) });
  const run = useMutation({ mutationFn: () => callHost('evaluate', { proposal_id: proposal.id }) });
  const reject = useMutation({ mutationFn: () => callHost('reject', { proposal_id: proposal.id }) });
  if (input.kind !== 'evaluation') return null;
  const pair = pairSchema.safeParse(proposal.result);
  return <article className="space-y-3 rounded-lg border border-border bg-surface p-4">
    <h2 className="font-display text-heading-3">{t('connector.evaluateTitle')}</h2>
    <dl className="space-y-2 text-body">
      <dt>{t('connector.original_version_id')}</dt><dd className="break-all">{originalId}</dd>
      <dt>{t('connector.candidate_version_id')}</dt><dd className="break-all">{candidateId}</dd>
      <dt>{t('connector.dataset')}</dt><dd className="break-all">{input.dataset_id}</dd>
      <dt>{t('connector.model')}</dt><dd>{original.data?.upstream_model}</dd>
    </dl>
    <p className="text-caption text-muted">{t('connector.evalLimit')}</p>
    <p>{t('connector.evalCost')}</p>
    <ConnectorError error={original.error ?? candidate.error ?? run.error ?? reject.error} />
    {original.isPending || candidate.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {proposal.status === 'pending' ? <Button loading={run.isPending} disabled={!original.data || !candidate.data} onClick={() => run.mutate()}>{t('connector.run')}</Button> : null}
    {proposal.status === 'uncertain' ? <p role="alert">{t('connector.uncertain')}</p> : null}
    {pair.success ? <ComparisonResults pair={pair.data} /> : null}
    <Button intent="secondary" loading={reject.isPending} onClick={() => reject.mutate()}>{t('connector.dismiss')}</Button>
  </article>;
}

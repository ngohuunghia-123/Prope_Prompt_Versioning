import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { getDatasetAttachments } from '@/features/prompt-lifecycle/evalApi';
import { useRevisionRuns } from '@/features/connectors/useRevisionRuns';
import { RunEvidence } from '@/features/connectors/RunEvidence';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function RevisionEvaluation({ promptId, versionId }: { promptId: string; versionId: string }) {
  const { t } = useTranslation(); const runs = useRevisionRuns(promptId, versionId);
  const attachments = useQuery({ queryKey: ['connector', 'attachments', promptId], queryFn: () => getDatasetAttachments(promptId) });
  return <section className="space-y-3">
    <h3 className="font-display text-heading-3">{t('connector.runOriginal')}</h3>
    <p>{t('connector.runHint')}</p>
    <ConnectorError error={attachments.error ?? runs.history.error ?? runs.start.error} />
    {attachments.isPending || runs.history.isPending ? <p role="status">{t('common.loading')}</p> : null}
    <ul className="list-inside list-disc text-body">{(attachments.data ?? []).map((item) => <li key={item.dataset_id}>{item.dataset?.name ?? item.dataset_id}</li>)}</ul>
    {attachments.data?.length === 0 ? <p>{t('connector.noAttachedDatasets')}</p> : null}
    <Button loading={runs.start.isPending} disabled={!attachments.data?.length || attachments.isError || runs.history.isPending || runs.history.isError || runs.uncertain || runs.history.data?.some((run) => ['queued', 'running'].includes(run.status))} onClick={() => runs.start.mutate()}>{t('connector.runSelected')}</Button>
    {runs.uncertain ? <p role="alert">{t('connector.uncertain')}</p> : null}
    {runs.history.data?.length === 0 ? <p>{t('connector.noRuns')}</p> : null}
    {runs.history.data?.length ? <Select label={t('connector.runHistory')} value={runs.runId} onValueChange={runs.setSelected}
      options={runs.history.data.map((run) => ({ value: run.run_id, label: t('connector.runOption', { id: run.run_id, status: run.status }) }))} /> : null}
    {runs.runId ? <RunEvidence key={runs.runId} runId={runs.runId} /> : null}
  </section>;
}

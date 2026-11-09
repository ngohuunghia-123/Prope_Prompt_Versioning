import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { getFolders } from '@/features/connectors/api';
import { callHost } from '@/features/connectors/bridge';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { getDatasets, getDatasetAttachments } from '@/features/prompt-lifecycle/evalApi';
import { DatasetEditorDialog } from '@/features/prompt-lifecycle/components/DatasetEditorDialog';

export function ConnectorDatasets({ promptId, namespace }: { promptId: string; namespace: string }) {
  const { t } = useTranslation(); const client = useQueryClient();
  const [creating, setCreating] = useState(false);
  const datasets = useQuery({ queryKey: ['connector', 'datasets'], queryFn: getDatasets });
  const attachments = useQuery({ queryKey: ['connector', 'attachments', promptId], queryFn: () => getDatasetAttachments(promptId) });
  const folders = useQuery({ queryKey: ['connector', 'folders'], queryFn: getFolders });
  const attach = useMutation({ mutationFn: (datasetIds: string[]) => callHost('attach_datasets', { prompt_id: promptId, dataset_ids: datasetIds }), onSuccess: () => client.invalidateQueries() });
  const selected = new Set((attachments.data ?? []).map((item) => item.dataset_id));
  return <section className="space-y-3">
    <h3 className="font-display text-heading-3">{t('connector.manageDatasets')}</h3>
    <p className="text-caption text-muted">{t('connector.datasetHint')}</p>
    <ConnectorError error={datasets.error ?? attachments.error ?? folders.error ?? attach.error} />
    {datasets.isPending || attachments.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {datasets.data?.length === 0 ? <p>{t('connector.noDatasets')}</p> : null}
    <div className="max-h-80 space-y-2 overflow-auto">{(datasets.data ?? []).map((dataset) => <div key={dataset.dataset_id} className="rounded-lg border border-border p-3">
      <Checkbox label={dataset.name} checked={selected.has(dataset.dataset_id)} disabled={attach.isPending || attachments.isPending || attachments.isError}
        onChange={(event) => attach.mutate(event.target.checked ? [...selected, dataset.dataset_id] : [...selected].filter((id) => id !== dataset.dataset_id))} />
      <p className="text-caption text-muted">{t('connector.caseCount', { count: dataset.case_count })}</p>
    </div>)}</div>
    <Button intent="secondary" onClick={() => setCreating(true)}>{t('lifecycle.evalDatasets.newDataset')}</Button>
    <DatasetEditorDialog open={creating} mode="create" promptId={promptId} defaultFolder={namespace} folders={(folders.data ?? []).map((folder) => folder.slug)}
      onClose={() => setCreating(false)} onSaved={() => { setCreating(false); void client.invalidateQueries(); }} />
  </section>;
}

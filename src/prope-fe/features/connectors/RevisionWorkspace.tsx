import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { getPrompt, getRevision } from '@/features/connectors/api';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { ConnectorDatasets } from '@/features/connectors/ConnectorDatasets';
import { RevisionEditor } from '@/features/connectors/RevisionEditor';
import { RevisionEvaluation } from '@/features/connectors/RevisionEvaluation';
import { ConnectorImprovement } from '@/features/connectors/ConnectorImprovement';
import { RevisionContentComparison } from '@/features/connectors/RevisionContentComparison';

export function RevisionWorkspace({ promptId, versionId }: { promptId: string; versionId: string }) {
  const { t } = useTranslation(); const [tab, setTab] = useState('content');
  const prompt = useQuery({ queryKey: ['connector', 'prompt', promptId], queryFn: () => getPrompt(promptId) });
  const revision = useQuery({ queryKey: ['connector', 'revision', versionId], queryFn: () => getRevision(versionId) });
  return <section className="space-y-4 rounded-lg border border-border bg-surface p-4">
    <h2 className="break-all font-display text-heading-3">{prompt.data?.model_name ?? promptId}</h2>
    <p className="break-all text-caption text-muted">{versionId}</p>
    <ConnectorError error={prompt.error ?? revision.error} />
    {prompt.isPending || revision.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {prompt.data && revision.data && revision.data.prompt_id === promptId ? <>
      <nav className="flex flex-wrap gap-2" aria-label={t('connector.workspaceNavigation')}>
        {['content', 'datasets', 'evaluation', 'improvement', 'compare'].map((value) => <Button key={value} intent={tab === value ? 'primary' : 'secondary'} aria-pressed={tab === value} onClick={() => setTab(value)}>{t(`connector.tabs.${value}`)}</Button>)}
      </nav>
      <div hidden={tab !== 'content'}><RevisionEditor key={JSON.stringify(revision.data)} revision={revision.data} /></div>
      {tab === 'datasets' ? <ConnectorDatasets promptId={promptId} namespace={prompt.data.namespace} /> : null}
      {tab === 'evaluation' ? <RevisionEvaluation promptId={promptId} versionId={versionId} /> : null}
      {tab === 'improvement' ? <ConnectorImprovement promptId={promptId} versionId={versionId} /> : null}
      {tab === 'compare' ? <RevisionContentComparison promptId={promptId} versionId={versionId} /> : null}
    </> : null}
  </section>;
}

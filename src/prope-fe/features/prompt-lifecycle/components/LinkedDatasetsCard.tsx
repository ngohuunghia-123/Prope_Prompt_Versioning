import { Database, Play } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import type { Dataset } from '@/features/prompt-lifecycle/types';

interface LinkedDatasetsCardProps { datasets: Dataset[]; running: boolean; onRun: () => void; }

export function LinkedDatasetsCard({ datasets, running, onRun }: LinkedDatasetsCardProps) {
  const { t } = useTranslation();
  const typeKeys = { golden: 'golden', regression: 'regression', 'red-team': 'redTeam' } as const;
  return <Card title={t('lifecycle.overview.evaluation.linkedDatasets')} action={<Button size="small" leadingIcon={<Play aria-hidden className="size-4" weight="fill" />} loading={running} onClick={onRun}>{t('lifecycle.overview.evaluation.runEvaluation')}</Button>}>{datasets.length ? <div className="space-y-3">{datasets.map((dataset) => <div key={dataset.id} className="flex items-center justify-between rounded-modal border border-border bg-subtle p-3"><div className="flex items-center gap-3"><Database aria-hidden className="size-5 text-secondary" /><div><p className="font-medium text-ink">{dataset.name}</p><p className="text-caption text-muted">{t('lifecycle.overview.evaluation.testCaseCount', { count: dataset.testCaseCount })}</p></div></div><StatusBadge tone={dataset.type === 'golden' ? 'active' : dataset.type === 'regression' ? 'pending' : 'disabled'}>{t(`lifecycle.dataset.types.${typeKeys[dataset.type]}`)}</StatusBadge></div>)}</div> : <p className="rounded-modal border border-dashed border-border p-6 text-center text-muted">{t('lifecycle.overview.evaluation.noLinkedDatasets')}</p>}</Card>;
}

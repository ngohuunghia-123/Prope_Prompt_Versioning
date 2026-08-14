import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import type { EvalRun } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface EvaluationRunCardProps { run: EvalRun; }

export function EvaluationRunCard({ run }: EvaluationRunCardProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const tone = run.recommendation === 'readyForReview' ? 'active' : run.recommendation === 'needsChanges' ? 'pending' : 'disabled';
  return <Card title={t('lifecycle.overview.evaluation.recentRuns')}><article className="rounded-modal border border-border bg-surface p-4"><div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><h4 className="font-medium text-ink">{run.datasetName}</h4><StatusBadge tone={tone}>{t(`lifecycle.overview.evaluation.recommendation.${run.recommendation}`)}</StatusBadge></div><p className="mt-1 text-caption text-muted">{t('lifecycle.overview.evaluation.runDateValue', { date: format.date(run.createdAt) })}</p><p className="text-caption text-muted">{t('lifecycle.overview.evaluation.runCases', { cases: run.caseCount, passed: run.caseCount - run.failures.length })}</p></div><div className="text-right"><p className="text-caption text-muted">{t('lifecycle.overview.evaluation.costDelta')}</p><p className={cn('font-medium', run.costDelta < 0 ? 'text-success-text' : 'text-danger-text')}>{run.costDelta > 0 ? '+' : ''}{format.percent(run.costDelta)}</p></div></div>{run.failures.length ? <div className="mt-4 border-t border-border pt-4"><h5 className="text-caption font-medium text-danger-text">{t('lifecycle.overview.evaluation.failures')}</h5><ul className="mt-2 space-y-1">{run.failures.slice(0, 3).map((failure) => <li key={failure.id} className="text-caption text-muted"><strong className="text-ink">{failure.caseName}:</strong> {failure.reason}</li>)}</ul></div> : null}</article></Card>;
}

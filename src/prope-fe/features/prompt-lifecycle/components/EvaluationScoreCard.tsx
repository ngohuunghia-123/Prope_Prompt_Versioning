import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import type { EvalRun } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface EvaluationScoreCardProps { run: EvalRun; }

export function EvaluationScoreCard({ run }: EvaluationScoreCardProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const score = Object.values(run.metrics).reduce((sum, value) => sum + value, 0) / Object.values(run.metrics).length;
  const tone = run.recommendation === 'readyForReview' ? 'active' : run.recommendation === 'needsChanges' ? 'pending' : 'disabled';
  return <Card title={t('lifecycle.overview.evaluation.overallScore')}><div className="flex flex-col items-center gap-5 py-6"><div className="grid size-36 place-items-center rounded-full border-8 border-primary/30"><div className="text-center"><strong className="font-display text-heading-1 font-normal text-ink">{format.percent(score)}</strong><p className="text-caption text-muted">{t('lifecycle.overview.evaluation.overall')}</p></div></div><StatusBadge tone={tone}>{t(`lifecycle.overview.evaluation.recommendation.${run.recommendation}`)}</StatusBadge></div></Card>;
}

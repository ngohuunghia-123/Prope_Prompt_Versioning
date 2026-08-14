import { useTranslation } from 'react-i18next';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import type { EvaluationOverview } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface EvaluationKpiGridProps {
  overview: EvaluationOverview;
}

export function EvaluationKpiGrid({ overview }: EvaluationKpiGridProps) {
  const { t, i18n } = useTranslation();
  const format = useLocaleFormatters();
  const decimal = new Intl.NumberFormat(i18n.resolvedLanguage ?? i18n.language, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const metrics = [
    { label: t('lifecycle.overview.evaluation.passRate'), value: format.percent(overview.passRate) },
    { label: t('lifecycle.overview.evaluation.averageScore'), value: t('lifecycle.overview.evaluation.scoreOutOfTen', { score: decimal.format(overview.averageScore) }) },
    { label: t('lifecycle.overview.evaluation.evalRuns'), value: format.number(overview.evalRuns) },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {metrics.map((metric) => <MetricTile key={metric.label} label={metric.label} value={metric.value} />)}
    </div>
  );
}

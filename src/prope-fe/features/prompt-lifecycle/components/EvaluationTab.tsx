import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { EvaluationDatasetTable } from '@/features/prompt-lifecycle/components/EvaluationDatasetTable';
import { EvaluationKpiGrid } from '@/features/prompt-lifecycle/components/EvaluationKpiGrid';
import { evaluationOverviewOptions } from '@/features/prompt-lifecycle/queries';

interface EvaluationTabProps {
  promptId: string;
  revisionId: string;
}

export function EvaluationTab({ promptId, revisionId }: EvaluationTabProps) {
  const { t } = useTranslation();
  const overviewQuery = useQuery(evaluationOverviewOptions(promptId, revisionId));

  if (overviewQuery.isPending) {
    return (
      <p role="status" className="py-12 text-center text-body text-muted">
        {t('lifecycle.overview.evaluation.loading')}
      </p>
    );
  }

  if (overviewQuery.isError) {
    return (
      <p role="alert" className="rounded-modal border border-danger bg-danger p-5 text-body text-danger-text">
        {t('lifecycle.overview.evaluation.loadError')}
      </p>
    );
  }

  const overview = overviewQuery.data;

  return (
    <section aria-label={t('lifecycle.overview.evaluation.summary')} className="grid gap-6">
      <EvaluationKpiGrid overview={overview} />
      {overview.datasets.length ? (
        <EvaluationDatasetTable datasets={overview.datasets} />
      ) : (
        <p className="rounded-modal border border-dashed border-border bg-surface p-8 text-center text-body text-muted">
          {t('lifecycle.overview.evaluation.noEvaluationData')}
        </p>
      )}
    </section>
  );
}

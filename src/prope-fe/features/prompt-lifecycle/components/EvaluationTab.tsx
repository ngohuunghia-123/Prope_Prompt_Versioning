import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { EvaluationKpiGrid } from '@/features/prompt-lifecycle/components/EvaluationKpiGrid';
import { EvaluationRevisionTrend } from '@/features/prompt-lifecycle/components/EvaluationRevisionTrend';
import { EvaluationSuiteTable } from '@/features/prompt-lifecycle/components/EvaluationSuiteTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import type { EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';
import { promptEvalRunsOptions } from '@/features/prompt-lifecycle/queries';

interface EvaluationTabProps {
  promptId: string;
  revisionId: string | null;
  /** `version_id` to the rail's label, so the trend can name its columns. */
  revisionLabels: Record<string, string>;
}

/** Newest first in, one run per suite out — the latest of each. */
function latestPerSuite(runs: EvalRunSummary[]): EvalRunSummary[] {
  const seen = new Map<string, EvalRunSummary>();
  for (const run of runs) {
    if (!seen.has(run.suite_id)) seen.set(run.suite_id, run);
  }
  return [...seen.values()];
}

/**
 * Whether this prompt survives its eval suites, and whether that is getting
 * better or worse.
 *
 * **One request, two answers.** The whole run history comes back in a single
 * call and is narrowed here: the KPI grid and the suite table read the selected
 * revision's runs, the trend reads all of them. Asking twice would let the
 * headline number and the last bar of the trend disagree by a race.
 */
export function EvaluationTab({ promptId, revisionId, revisionLabels }: EvaluationTabProps) {
  const { t } = useTranslation();
  const query = useQuery(promptEvalRunsOptions(promptId));

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const all = query.data;
  const forRevision = revisionId === null ? [] : all.filter((run) => run.version_id === revisionId);

  return (
    <section aria-label={t('lifecycle.insights.evaluation.summary')} className="grid gap-6">
      {forRevision.length ? (
        <>
          <EvaluationKpiGrid runs={forRevision} />
          <EvaluationSuiteTable runs={latestPerSuite(forRevision)} />
        </>
      ) : (
        <p className="rounded-modal border border-dashed border-border bg-surface p-8 text-center text-body text-muted">
          {t(
            all.length
              ? 'lifecycle.insights.evaluation.emptyRevision'
              : 'lifecycle.insights.evaluation.emptyPrompt',
          )}
        </p>
      )}

      <EvaluationRevisionTrend runs={all} revisionLabels={revisionLabels} selectedVersionId={revisionId} />
    </section>
  );
}

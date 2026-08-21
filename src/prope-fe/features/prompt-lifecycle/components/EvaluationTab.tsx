import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import { EvaluationDatasetDrawer } from '@/features/prompt-lifecycle/components/EvaluationDatasetDrawer';
import { EvaluationKpiGrid } from '@/features/prompt-lifecycle/components/EvaluationKpiGrid';
import { EvaluationRevisionTrend } from '@/features/prompt-lifecycle/components/EvaluationRevisionTrend';
import { EvaluationSuiteTable } from '@/features/prompt-lifecycle/components/EvaluationSuiteTable';
import { EvaluationRunDrawer } from '@/features/prompt-lifecycle/components/EvaluationRunDrawer';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptEvalRunsOptions } from '@/features/prompt-lifecycle/queries';
import { latestEvaluationRuns } from '@/features/prompt-lifecycle/evaluationEvidence';
import type { EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';

interface EvaluationTabProps {
  promptId: string;
  revisionId: string | null;
  /** `version_id` to the rail's label, so the trend can name its columns. */
  revisionLabels: Record<string, string>;
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
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRun, setSelectedRun] = useState<EvalRunSummary>();
  const query = useQuery(promptEvalRunsOptions(promptId));

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const all = query.data;
  const forRevision = revisionId === null ? [] : all.filter((run) => run.version_id === revisionId);

  return (
    <section aria-label={t('lifecycle.insights.evaluation.summary')} className="w-full min-w-0 max-w-full divide-y divide-border overflow-hidden">
      {forRevision.length ? (
        <>
          <EvaluationKpiGrid runs={forRevision} />
          <EvaluationSuiteTable runs={latestEvaluationRuns(forRevision)} onSelect={setSelectedRun} />
        </>
      ) : (
        <div className="grid justify-items-center gap-4 border-y border-dashed border-border p-8 text-center">
          <p className="max-w-2xl text-body text-muted">{t(all.length ? 'lifecycle.insights.evaluation.emptyRevision' : 'lifecycle.insights.evaluation.emptyPrompt')}</p>
          <Button type="button" onClick={() => setDrawerOpen(true)}>{t('lifecycle.insights.evaluation.quickRun.action')}</Button>
        </div>
      )}

      <EvaluationRevisionTrend runs={all} revisionLabels={revisionLabels} selectedVersionId={revisionId} />
      {revisionId ? <EvaluationDatasetDrawer open={drawerOpen} promptId={promptId} revisionId={revisionId} onClose={() => setDrawerOpen(false)} /> : null}
      <EvaluationRunDrawer run={selectedRun} onClose={() => setSelectedRun(undefined)} />
    </section>
  );
}

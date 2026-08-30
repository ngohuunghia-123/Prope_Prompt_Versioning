import { useQuery } from '@tanstack/react-query';
import { ClockCounterClockwise } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { EvaluationRunDrawer } from '@/features/prompt-lifecycle/components/EvaluationRunDrawer';
import { EvaluationSuiteTable } from '@/features/prompt-lifecycle/components/EvaluationSuiteTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { latestEvaluationRuns } from '@/features/prompt-lifecycle/evaluationEvidence';
import { promptEvalRunsOptions } from '@/features/prompt-lifecycle/queries';
import type { EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';

interface EvaluationTabProps { promptId: string; revisionId: string; revisionLabels: Record<string, string>; }

export function EvaluationTab({ promptId, revisionId }: EvaluationTabProps) {
  const { t } = useTranslation();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedRun, setSelectedRun] = useState<EvalRunSummary>();
  const query = useQuery(promptEvalRunsOptions(promptId));
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const runs = latestEvaluationRuns(query.data.filter((run) => run.version_id === revisionId));
  const completed = runs.filter((run) => run.status === 'completed');
  const passed = completed.reduce((total, run) => total + run.pass_count, 0);
  const failed = completed.reduce((total, run) => total + run.fail_count + run.error_count, 0);
  const issues = runs.filter((run) => run.fail_count > 0 || run.error_count > 0 || run.status === 'refused' || run.status === 'interrupted').slice(0, 3);
  return (
    <section aria-labelledby="evaluation-heading" className="mx-auto grid w-full max-w-(--container-content) gap-5 p-4 sm:p-6">
      <div className="rounded-modal border border-border bg-surface p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 id="evaluation-heading" tabIndex={-1} className="font-display text-heading-2 text-ink">{t('lifecycle.surface.evaluation.title')}</h1><p className="mt-1 text-body text-muted">{runs.length ? t('lifecycle.surface.evaluation.latest') : t('lifecycle.surface.evaluation.neverRun')}</p></div><Button type="button" intent="ghost" size="small" leadingIcon={<ClockCounterClockwise aria-hidden className="size-4" />} onClick={() => setHistoryOpen(true)}>{t('lifecycle.surface.evaluation.history')}</Button></div>
        {runs.length ? <dl className="mt-5 grid gap-3 sm:grid-cols-2"><div className="rounded-control bg-subtle p-4"><dt className="text-caption text-muted">{t('lifecycle.surface.evaluation.passed')}</dt><dd className="mt-1 font-display text-heading-2 text-success-text">{passed}</dd></div><div className="rounded-control bg-subtle p-4"><dt className="text-caption text-muted">{t('lifecycle.surface.evaluation.failed')}</dt><dd className="mt-1 font-display text-heading-2 text-danger-text">{failed}</dd></div></dl> : null}
      </div>
      {issues.length ? <section className="rounded-modal border border-warning-strong bg-warning p-5"><h2 className="font-display text-heading-3 text-warning-text">{t('lifecycle.surface.evaluation.issues')}</h2><ul className="mt-3 grid gap-2">{issues.map((run) => <li key={run.run_id}><button type="button" className="w-full rounded-control bg-surface p-3 text-left text-body text-ink focus-visible:outline-2 focus-visible:outline-focus" onClick={() => setSelectedRun(run)}>{run.suite_name ?? t('lifecycle.surface.evaluation.unnamedSuite')} · {t(`lifecycle.insights.runStatus.${run.status}`)}</button></li>)}</ul></section> : runs.length ? <p className="rounded-modal border border-border bg-surface p-5 text-body text-muted">{t('lifecycle.surface.evaluation.noIssues')}</p> : null}
      <Drawer open={historyOpen} onClose={() => setHistoryOpen(false)} side="right" size="wide" title={t('lifecycle.surface.evaluation.history')}><div className="h-full overflow-y-auto"><EvaluationSuiteTable runs={query.data} onSelect={setSelectedRun} /></div></Drawer>
      <EvaluationRunDrawer run={selectedRun} onClose={() => setSelectedRun(undefined)} />
    </section>
  );
}

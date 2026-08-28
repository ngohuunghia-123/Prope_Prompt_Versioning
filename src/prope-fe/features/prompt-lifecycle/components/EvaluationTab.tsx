import { useQuery } from '@tanstack/react-query';
import { CircleNotch, ClockCounterClockwise } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { EvaluationRunDrawer } from '@/features/prompt-lifecycle/components/EvaluationRunDrawer';
import { EvaluationSuiteTable } from '@/features/prompt-lifecycle/components/EvaluationSuiteTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { isTerminal } from '@/features/prompt-lifecycle/evalTypes';
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

  const revisionRuns = query.data.filter((run) => run.version_id === revisionId);
  // **A run that has been started but has not finished is evidence too.** The
  // start endpoint answers 202 and the executor picks the run up out of band, so
  // somebody who presses "Chạy kiểm thử" and comes straight here arrives before
  // any case has been written. Listing only settled runs made that indis-
  // tinguishable from never having evaluated at all, and the person had no way
  // to tell whether their run was lost.
  const inFlight = revisionRuns.filter((run) => !isTerminal(run.status));
  // Counted from the newest COMPLETED run per suite rather than the newest run
  // outright: `latestEvaluationRuns` keeps one row per suite, so a fresh queued
  // run would otherwise shadow the finished one it is re-running and drop the
  // tiles to 0/0 for the duration — reading as "everything regressed" while
  // nothing had happened yet.
  const runs = latestEvaluationRuns(revisionRuns.filter((run) => run.status === 'completed'));
  const settled = latestEvaluationRuns(revisionRuns.filter((run) => isTerminal(run.status)));
  const passed = runs.reduce((total, run) => total + run.pass_count, 0);
  const failed = runs.reduce((total, run) => total + run.fail_count + run.error_count, 0);
  const issues = settled.filter((run) => run.fail_count > 0 || run.error_count > 0 || run.status === 'refused' || run.status === 'interrupted').slice(0, 3);
  return (
    <section aria-labelledby="evaluation-heading" className="mx-auto grid w-full max-w-(--container-content) gap-5 p-4 sm:p-6">
      <div className="rounded-modal border border-border bg-surface p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 id="evaluation-heading" tabIndex={-1} className="font-display text-heading-2 text-ink">{t('lifecycle.surface.evaluation.title')}</h1><p className="mt-1 text-body text-muted">{revisionRuns.length ? t('lifecycle.surface.evaluation.latest') : t('lifecycle.surface.evaluation.neverRun')}</p></div><Button type="button" intent="ghost" size="small" leadingIcon={<ClockCounterClockwise aria-hidden className="size-4" />} onClick={() => setHistoryOpen(true)}>{t('lifecycle.surface.evaluation.history')}</Button></div>
        {runs.length ? <dl className="mt-5 grid gap-3 sm:grid-cols-2"><div className="rounded-control bg-subtle p-4"><dt className="text-caption text-muted">{t('lifecycle.surface.evaluation.passed')}</dt><dd className="mt-1 font-display text-heading-2 text-success-text">{passed}</dd></div><div className="rounded-control bg-subtle p-4"><dt className="text-caption text-muted">{t('lifecycle.surface.evaluation.failed')}</dt><dd className="mt-1 font-display text-heading-2 text-danger-text">{failed}</dd></div></dl> : null}
      </div>
      {/* Above the issues, because it is the newer fact and the one the person
          came back to check. Each row opens the same run drawer, which polls the
          run and fills in its cases as the executor writes them — so "is it
          still going?" is answerable without going back to the run page, whose
          own record of what was started does not survive a refresh. */}
      {inFlight.length ? (
        <section className="rounded-modal border border-border bg-surface p-5">
          <h2 className="font-display text-heading-3 text-ink">{t('lifecycle.surface.evaluation.inFlight')}</h2>
          <p className="mt-1 text-caption text-muted">{t('lifecycle.surface.evaluation.inFlightHint')}</p>
          <ul className="mt-3 grid gap-2">
            {inFlight.map((run) => (
              <li key={run.run_id}>
                <button
                  type="button"
                  className="flex w-full items-center gap-3 rounded-control bg-subtle p-3 text-left text-body text-ink focus-visible:outline-2 focus-visible:outline-focus"
                  onClick={() => setSelectedRun(run)}
                >
                  <CircleNotch aria-hidden className="size-4 shrink-0 animate-spin text-muted motion-reduce:animate-none" />
                  <span>{run.suite_name ?? t('lifecycle.surface.evaluation.unnamedSuite')} · {t(`lifecycle.insights.runStatus.${run.status}`)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {issues.length ? <section className="rounded-modal border border-warning-strong bg-warning p-5"><h2 className="font-display text-heading-3 text-warning-text">{t('lifecycle.surface.evaluation.issues')}</h2><ul className="mt-3 grid gap-2">{issues.map((run) => <li key={run.run_id}><button type="button" className="w-full rounded-control bg-surface p-3 text-left text-body text-ink focus-visible:outline-2 focus-visible:outline-focus" onClick={() => setSelectedRun(run)}>{run.suite_name ?? t('lifecycle.surface.evaluation.unnamedSuite')} · {t(`lifecycle.insights.runStatus.${run.status}`)}</button></li>)}</ul></section> : runs.length ? <p className="rounded-modal border border-border bg-surface p-5 text-body text-muted">{t('lifecycle.surface.evaluation.noIssues')}</p> : null}
      <Drawer open={historyOpen} onClose={() => setHistoryOpen(false)} side="right" size="wide" title={t('lifecycle.surface.evaluation.history')}><div className="h-full overflow-y-auto"><EvaluationSuiteTable runs={query.data} onSelect={setSelectedRun} /></div></Drawer>
      <EvaluationRunDrawer run={selectedRun} onClose={() => setSelectedRun(undefined)} />
    </section>
  );
}

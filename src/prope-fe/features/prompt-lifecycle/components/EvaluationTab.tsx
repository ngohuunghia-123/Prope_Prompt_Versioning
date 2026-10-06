import { useQuery } from '@tanstack/react-query';
import { CircleNotch } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Drawer } from '@/components/ui/Drawer';
import { EvalWorkspacePanel } from '@/features/prompt-lifecycle/components/EvalWorkspacePanel';
import { EvaluationRunDrawer } from '@/features/prompt-lifecycle/components/EvaluationRunDrawer';
import { EvaluationRunEvidence } from '@/features/prompt-lifecycle/components/EvaluationRunEvidence';
import { EvaluationSuiteTable } from '@/features/prompt-lifecycle/components/EvaluationSuiteTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { isTerminal } from '@/features/prompt-lifecycle/evalTypes';
import { promptEvalRunsOptions } from '@/features/prompt-lifecycle/queries';
import type { EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';

interface EvaluationTabProps {
  prompt: PromptDetail;
  revision: Revision;
  revisionLabels: Record<string, string>;
}

/** The evaluation tab: the workspace (attach test sets, run, watch results)
 * followed by the evidence of what already ran on this revision. */
export function EvaluationTab({ prompt, revision }: EvaluationTabProps) {
  const { t } = useTranslation();
  const promptId = prompt.id;
  const revisionId = revision.id;
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedRun, setSelectedRun] = useState<EvalRunSummary>();
  const [selection, setSelection] = useState<{ versionId: string; runId: string }>();
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
  const evidenceRun = selection?.versionId === revisionId
    ? revisionRuns.find((run) => run.run_id === selection.runId)
    : revisionRuns[0];
  const selectEvidenceRun = (runId: string) => setSelection({ versionId: revisionId, runId });
  return (
    <section aria-label={t('lifecycle.surface.evaluation.title')} className="mx-auto flex w-full max-w-(--container-content) flex-col gap-5 p-4 sm:p-6 navigation:max-h-full navigation:min-h-0 navigation:overflow-hidden">
      {/* The workspace first: on the path that ends here — saving in the
          composer — picking test sets and running them is the reason the person
          came. Its controls (suggest, history, draft, new) live in the dataset
          panel's own column, and once the revision has run the tab defaults to
          a results view where those controls hide until "Chạy bộ kiểm thử mới"
          brings them back. The tiles, in-flight list and issues render in the
          workspace's right column, beside the console. */}
      <EvalWorkspacePanel
        prompt={prompt}
        revision={revision}
        onOpenHistory={() => setHistoryOpen(true)}
        activeRunId={evidenceRun?.run_id}
        onSelectRun={selectEvidenceRun}
        results={
          <>
            {/* Above the issues, because it is the newer fact and the one the person
                came back to check. Each row opens the same run drawer, which polls the
                run and fills in its cases as the executor writes them. */}
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
                        onClick={() => { setSelectedRun(run); selectEvidenceRun(run.run_id); }}
                      >
                        <CircleNotch aria-hidden className="size-4 shrink-0 animate-spin text-muted motion-reduce:animate-none" />
                        <span>{run.suite_name ?? t('lifecycle.surface.evaluation.unnamedSuite')} · {t(`lifecycle.insights.runStatus.${run.status}`)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            <EvaluationRunEvidence
              promptId={promptId}
              versionId={revisionId}
              runs={revisionRuns}
              selected={evidenceRun}
              onSelect={selectEvidenceRun}
              onOpenRun={setSelectedRun}
            />
          </>
        }
      />
      <Drawer open={historyOpen} onClose={() => setHistoryOpen(false)} side="right" size="wide" title={t('lifecycle.surface.evaluation.history')}><div className="h-full overflow-y-auto"><EvaluationSuiteTable runs={query.data} onSelect={(run) => { setSelectedRun(run); if (run.version_id === revisionId) selectEvidenceRun(run.run_id); }} /></div></Drawer>
      <EvaluationRunDrawer run={selectedRun} onClose={() => setSelectedRun(undefined)} />
    </section>
  );
}

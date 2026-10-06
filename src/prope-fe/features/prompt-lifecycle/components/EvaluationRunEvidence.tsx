import { useTranslation } from 'react-i18next';
import { Select } from '@/components/ui/Select';
import { EvalAnalysisBrief } from '@/features/prompt-lifecycle/components/EvalAnalysisBrief';
import type { EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface EvaluationRunEvidenceProps {
  promptId: string;
  versionId: string;
  runs: EvalRunSummary[];
  selected?: EvalRunSummary;
  onSelect: (runId: string) => void;
  onOpenRun: (run: EvalRunSummary) => void;
}

/** Counts, issues and analysis all belong to the same selected run. */
export function EvaluationRunEvidence({ promptId, versionId, runs, selected, onSelect, onOpenRun }: EvaluationRunEvidenceProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();
  const canAnalyze = selected?.status === 'completed';
  const hasIssues = selected && (selected.fail_count > 0 || selected.error_count > 0 || selected.status === 'refused' || selected.status === 'interrupted');
  return (
    <>
      {runs.length ? (
        <Select
          label={t('lifecycle.surface.evaluation.selectedRun')}
          value={selected?.run_id ?? ''}
          onValueChange={onSelect}
          options={runs.map((run) => ({
            value: run.run_id,
            label: t('lifecycle.surface.evaluation.runOption', {
              suite: run.dataset_name ?? run.suite_name ?? t('lifecycle.surface.evaluation.unnamedSuite'),
              time: run.started_at || run.finished_at ? format.dateTime(run.started_at ?? run.finished_at ?? '') : t('lifecycle.surface.evaluation.notStarted'),
              status: t(`lifecycle.insights.runStatus.${run.status}`),
            }),
          }))}
        />
      ) : null}
      {selected ? (
        <dl className="grid grid-cols-2 gap-3">
          <div className="rounded-control bg-subtle p-4">
            <dt className="text-caption text-muted">{t('lifecycle.surface.evaluation.passed')}</dt>
            <dd className="mt-1 font-display text-heading-2 text-success-text">{format.number(selected.pass_count)}</dd>
          </div>
          <div className="rounded-control bg-subtle p-4">
            <dt className="text-caption text-muted">{t('lifecycle.surface.evaluation.failed')}</dt>
            <dd className="mt-1 font-display text-heading-2 text-danger-text">{format.number(selected.fail_count + selected.error_count)}</dd>
          </div>
        </dl>
      ) : null}
      {hasIssues && selected ? (
        <section className="rounded-modal border border-warning-strong bg-warning p-5">
          <h2 className="font-display text-heading-3 text-warning-text">{t('lifecycle.surface.evaluation.issues')}</h2>
          <button type="button" className="mt-3 w-full rounded-control bg-surface p-3 text-left text-body text-ink focus-visible:outline-2 focus-visible:outline-focus" onClick={() => onOpenRun(selected)}>
            {selected.suite_name ?? t('lifecycle.surface.evaluation.unnamedSuite')} · {t(`lifecycle.insights.runStatus.${selected.status}`)}
          </button>
        </section>
      ) : canAnalyze ? (
        <p className="rounded-modal border border-border bg-surface p-5 text-body text-muted">{t('lifecycle.surface.evaluation.noIssues')}</p>
      ) : null}
      <EvalAnalysisBrief
        key={`${versionId}:${selected?.run_id ?? ''}`}
        promptId={promptId}
        versionId={versionId}
        runId={selected?.run_id}
        canAnalyze={canAnalyze}
        disabledReason={!selected ? t('lifecycle.evalAdvisor.noRuns') : !canAnalyze ? t('lifecycle.evalAdvisor.selectedRunIncomplete') : undefined}
      />
    </>
  );
}

import { CheckCircle, CircleNotch, Prohibit, WarningCircle, XCircle } from '@phosphor-icons/react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { EvaluationTracePanel } from '@/features/prompt-lifecycle/components/EvaluationTracePanel';
import { cn } from '@/lib/cn';
import {
  isTerminal,
  type EvalCaseOutcome,
  type EvalCaseResult,
  type EvalSuiteReport,
} from '@/features/prompt-lifecycle/evalTypes';

interface EvalRunResultsProps {
  reports: EvalSuiteReport[];
}

function OutcomeIcon({ outcome }: { outcome: EvalCaseOutcome }) {
  if (outcome === 'pass') {
    return <CheckCircle aria-hidden weight="fill" className="size-4 shrink-0 text-success-text" />;
  }
  if (outcome === 'fail') {
    return <XCircle aria-hidden weight="fill" className="size-4 shrink-0 text-danger-text" />;
  }
  // An error is not a fail (A-057) and must not be drawn as one — the prompt
  // may be perfect and the provider merely unreachable.
  return <WarningCircle aria-hidden weight="fill" className="size-4 shrink-0 text-warning-text" />;
}

function SuiteStrip({
  reports,
  selectedId,
  onSelect,
}: {
  reports: EvalSuiteReport[];
  selectedId: string;
  onSelect: (runId: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap gap-2 rounded-modal border border-border bg-surface p-2 shadow-panel">
      {reports.map(({ handle, run, cases }) => {
        const selected = handle.run_id === selectedId;
        const status = run?.status ?? 'queued';
        const running = !isTerminal(status);
        const passed = cases.filter((entry) => entry.outcome === 'pass').length;
        return (
          <button
            key={handle.run_id}
            type="button"
            onClick={() => onSelect(handle.run_id)}
            aria-pressed={selected}
            className={cn(
              'grid min-w-44 gap-1 rounded-xl border px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-focus',
              selected ? 'border-focus bg-accent-soft' : 'border-border bg-canvas hover:bg-subtle',
            )}
          >
            <span className="flex items-center gap-2">
              {running ? (
                <CircleNotch
                  aria-hidden
                  className="size-4 shrink-0 animate-spin text-muted"
                  weight="bold"
                />
              ) : status === 'refused' ? (
                <Prohibit aria-hidden weight="fill" className="size-4 shrink-0 text-warning-text" />
              ) : (
                <OutcomeIcon
                  outcome={
                    (run?.fail_count ?? 0) > 0
                      ? 'fail'
                      : (run?.error_count ?? 0) > 0
                        ? 'error'
                        : 'pass'
                  }
                />
              )}
              <span className="truncate text-body font-medium text-ink">{handle.suite_name}</span>
            </span>
            <span className="text-caption text-muted">
              {t('lifecycle.evalRun.suiteVersion', { version: handle.suite_version })}
              {handle.role === 'baseline'
                ? ` · ${t('lifecycle.evalRun.role.baseline')}`
                : null}
            </span>
            <span className="text-caption font-medium text-ink">
              {running
                ? t(`lifecycle.evalRun.status.${status}`)
                : status === 'refused'
                  ? t('lifecycle.evalRun.status.refused')
                  : t('lifecycle.evalRun.passCount', { passed, total: cases.length })}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function CaseDetail({ result, caseName }: { result: EvalCaseResult; caseName: string }) {
  const { t } = useTranslation();
  return (
    <div className="grid content-start gap-4 p-4">
      <div className="grid gap-1">
        <h3 className="text-body font-semibold text-ink">{caseName}</h3>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
          <span className="flex items-center gap-1.5">
            <OutcomeIcon outcome={result.outcome} />
            {t(`lifecycle.evalRun.outcome.${result.outcome}`)}
          </span>
          {result.latency_ms !== null ? (
            <span>{t('lifecycle.evalRun.latency', { ms: result.latency_ms })}</span>
          ) : null}
          {result.input_tokens !== null || result.output_tokens !== null ? (
            <span>
              {t('lifecycle.evalRun.tokens', {
                input: result.input_tokens ?? 0,
                output: result.output_tokens ?? 0,
              })}
            </span>
          ) : null}
          {result.attempt_count > 1 ? (
            <span>{t('lifecycle.evalRun.attempts', { count: result.attempt_count })}</span>
          ) : null}
        </p>
      </div>

      {result.error_code ? (
        <div className="grid gap-1 rounded-lg bg-warning/10 px-3 py-2 text-warning-text">
          {result.error_detail ? (
            <>
              <p className="break-words whitespace-pre-wrap text-body font-medium">
                {t('lifecycle.evalRun.errorDetail', { detail: result.error_detail })}
              </p>
              <p className="text-caption opacity-80">
                {t('lifecycle.evalRun.errorCode', { code: result.error_code })}
              </p>
            </>
          ) : (
            <p className="text-caption">
              {t('lifecycle.evalRun.errorCode', { code: result.error_code })}
            </p>
          )}
        </div>
      ) : null}

      <section className="grid gap-2">
        <h4 className="text-overline font-bold uppercase tracking-navigation-overline text-muted">
          {t('lifecycle.evalRun.assertions')}
        </h4>
        {result.assertion_results.length === 0 ? (
          <p className="text-caption text-muted">{t('lifecycle.evalRun.noAssertions')}</p>
        ) : (
          <ul className="grid gap-1.5">
            {result.assertion_results.map((assertion, index) => (
              <li
                key={`${assertion.type}-${index}`}
                className="flex items-start gap-2 rounded-lg border border-border bg-canvas px-3 py-2"
              >
                {assertion.passed ? (
                  <CheckCircle
                    aria-hidden
                    weight="fill"
                    className="mt-0.5 size-4 shrink-0 text-success-text"
                  />
                ) : (
                  <XCircle
                    aria-hidden
                    weight="fill"
                    className="mt-0.5 size-4 shrink-0 text-danger-text"
                  />
                )}
                <span className="grid min-w-0 gap-0.5">
                  <span className="font-mono text-caption text-ink">{assertion.type}</span>
                  {assertion.detail ? (
                    <span className="text-caption text-muted">{assertion.detail}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid min-w-0 gap-2">
        <h4 className="text-overline font-bold uppercase tracking-navigation-overline text-muted">
          {t('lifecycle.evalRun.output')}
        </h4>
        {result.output_content ? (
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-canvas p-3 text-caption text-ink">
            {result.output_content}
          </pre>
        ) : (
          <p className="text-caption text-muted">{t('lifecycle.evalRun.noOutput')}</p>
        )}
      </section>
      <EvaluationTracePanel runId={result.run_id} caseResultId={result.case_result_id} />
    </div>
  );
}

/**
 * Runs, their cases, and one case in detail.
 *
 * Written against `evaluation`'s own shapes. It replaces three mock-workspace
 * components that rendered an `expectedOutput` per case and a score across
 * accuracy / relevance / format / safety; the module has neither. A case
 * carries deterministic assertions and one outcome, and four dimensions of
 * score would be numbers with nothing behind them.
 *
 * Cases appear while the run is still going, because the executor writes a
 * `case_result` row as each one finishes. A twenty-case suite therefore fills
 * in rather than sitting behind a spinner for two minutes.
 */
export function EvalRunResults({ reports }: EvalRunResultsProps) {
  const { t } = useTranslation();
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedCaseId, setSelectedCaseId] = useState('');

  const selected = useMemo(
    () => reports.find((report) => report.handle.run_id === selectedRunId) ?? reports[0],
    [reports, selectedRunId],
  );

  const caseNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const entry of selected?.suite?.cases ?? []) names.set(entry.case_id, entry.name);
    return names;
  }, [selected]);

  const selectedCase = useMemo(
    () =>
      selected?.cases.find((entry) => entry.case_id === selectedCaseId) ?? selected?.cases[0],
    [selected, selectedCaseId],
  );

  useEffect(() => {
    if (!selectedRunId && reports[0]) setSelectedRunId(reports[0].handle.run_id);
  }, [reports, selectedRunId]);

  if (reports.length === 0) return null;

  const status = selected?.run?.status ?? 'queued';

  return (
    <div className="grid min-h-0 gap-3">
      <SuiteStrip
        reports={reports}
        selectedId={selected?.handle.run_id ?? ''}
        onSelect={(runId) => {
          setSelectedRunId(runId);
          setSelectedCaseId('');
        }}
      />

      {/* Same viewport cap as the dataset tree: a long case list or a long
          output scrolls in its own pane instead of stretching the page. */}
      <div className="grid min-h-0 overflow-hidden rounded-modal border border-border bg-surface shadow-panel lg:max-h-[calc(100dvh-18rem)] lg:grid-cols-[minmax(14rem,0.62fr)_minmax(0,1.38fr)]">
        <div className="min-h-0 overflow-y-auto border-b border-border lg:border-b-0 lg:border-r">
          {selected?.cases.length ? (
            <ul>
              {selected.cases.map((result) => {
                const active = result.case_id === selectedCase?.case_id;
                return (
                  <li key={result.case_result_id}>
                    <button
                      type="button"
                      onClick={() => setSelectedCaseId(result.case_id)}
                      aria-pressed={active}
                      className={cn(
                        'flex w-full items-center gap-2 border-b border-border/60 px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-focus',
                        active ? 'bg-accent-soft' : 'hover:bg-subtle',
                      )}
                    >
                      <OutcomeIcon outcome={result.outcome} />
                      <span className="truncate text-caption text-ink">
                        {caseNames.get(result.case_id) ?? result.case_id}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="p-4 text-caption text-muted">
              {isTerminal(status)
                ? t('lifecycle.evalRun.noCases')
                : t('lifecycle.evalRun.waitingForCases')}
            </p>
          )}
        </div>

        <div className="min-h-0 min-w-0 overflow-y-auto">
          {/* A refusal names why, but it is not the whole story: whatever the
              probe dispatched before the run was refused is recorded below the
              banner, so the person can read the response that tripped the
              check and judge whether the suite or the prompt is wrong. */}
          {selected?.run?.status === 'refused' ? (
            <p className="m-4 rounded-lg bg-warning/10 px-3 py-2 text-caption text-warning-text">
              {t('lifecycle.evalRun.refused', {
                reason: selected.run.refused_reason
                  ? t(`lifecycle.evalRun.refusedReason.${selected.run.refused_reason}`, {
                      defaultValue: selected.run.refused_reason,
                    })
                  : '',
              })}
            </p>
          ) : null}
          {selectedCase ? (
            <CaseDetail
              result={selectedCase}
              caseName={caseNames.get(selectedCase.case_id) ?? selectedCase.case_id}
            />
          ) : (
            <p className="p-4 text-caption text-muted">
              {isTerminal(status)
                ? t('lifecycle.evalRun.noCases')
                : t('lifecycle.evalRun.waitingForCases')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

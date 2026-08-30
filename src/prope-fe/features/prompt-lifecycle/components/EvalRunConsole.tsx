import { Play, Stop } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { EvalRunResults } from '@/features/prompt-lifecycle/components/EvalRunResults';
import type { EvalSuiteReport } from '@/features/prompt-lifecycle/evalTypes';

interface EvalRunConsoleProps {
  attachedCount: number;
  runnable: boolean;
  runDisabledReason: string | undefined;
  busy: boolean;
  /** Session-local: only runs this tab started, not the revision's history. */
  hasReports: boolean;
  reports: EvalSuiteReport[];
  /** Suite reports render only in the new-run state; the results view keeps
   * its evidence in the tiles and issue list instead. */
  showReports: boolean;
  /** Exits the new-run state back to the results view. Absent when there are
   * no results to return to. */
  onCancel?: () => void;
  /** At least one of this tab's runs is still queued or running, so a stop
   * button is honest here. Absent while nothing the tab started is in flight. */
  cancellable?: boolean;
  cancelling?: boolean;
  onCancelRun?: () => void;
  onRun: () => void;
}

/** The right half of the eval workspace: the run button and what running produced.
 *
 * Runs started elsewhere — a previous visit, the release gate — are evidence the
 * tab shows in its own sections; this console only reports what it started, so a
 * person who just pressed the button sees their runs fill in without hunting. */
export function EvalRunConsole({
  attachedCount,
  runnable,
  runDisabledReason,
  busy,
  hasReports,
  reports,
  showReports,
  onCancel,
  cancellable,
  cancelling,
  onCancelRun,
  onRun,
}: EvalRunConsoleProps) {
  const { t } = useTranslation();
  return (
    <div className="grid min-w-0 content-start gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-modal border border-border bg-surface px-4 py-3 shadow-panel">
        <div className="grid gap-0.5">
          <h2 className="text-body font-semibold text-ink">{t('lifecycle.evalRun.title')}</h2>
          <p className="text-caption text-muted">{t('lifecycle.evalRun.description')}</p>
        </div>
        <div className="flex items-center gap-2">
          {onCancel ? (
            <Button type="button" intent="ghost" onClick={onCancel}>
              {t('lifecycle.evalRun.cancel')}
            </Button>
          ) : null}
          {cancellable && onCancelRun ? (
            <Button
              type="button"
              intent="danger"
              loading={cancelling}
              leadingIcon={<Stop aria-hidden weight="fill" className="size-4" />}
              onClick={onCancelRun}
            >
              {t('lifecycle.evalRun.cancelRun')}
            </Button>
          ) : null}
          <Button
            type="button"
            loading={busy}
            disabled={!runnable}
            disabledReason={runDisabledReason}
            leadingIcon={<Play aria-hidden weight="fill" className="size-4" />}
            onClick={onRun}
          >
            {t('lifecycle.evalRun.run', { count: attachedCount })}
          </Button>
        </div>
      </div>
      {showReports && hasReports ? (
        <EvalRunResults reports={reports} />
      ) : (
        <div className="grid place-items-center rounded-modal border border-dashed border-border bg-surface p-10 text-center">
          <p className="text-body text-ink">
            {attachedCount === 0
              ? t('lifecycle.evalRun.pickSomething')
              : t('lifecycle.evalRun.readyToRun', { count: attachedCount })}
          </p>
          <p className="mt-1 max-w-prose text-caption text-muted">
            {t('lifecycle.evalRun.skipIsFine')}
          </p>
        </div>
      )}
    </div>
  );
}

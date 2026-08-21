import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import { LogDetailDrawer } from '@/features/prompt-lifecycle/components/LogDetailDrawer';
import { LogFilters } from '@/features/prompt-lifecycle/components/LogFilters';
import { PromptLogTable } from '@/features/prompt-lifecycle/components/PromptLogTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { usePromptLogs } from '@/features/prompt-lifecycle/components/usePromptLogs';

interface LogsTabProps {
  promptId: string;
  revisionId: string | null;
  revisionLabel: string | null;
}

/**
 * Every call this prompt has served, newest first.
 *
 * Empty is the ordinary state of a prompt nobody has released, so it reads as an
 * explanation rather than as a failure — and with the source filter on
 * `gateway`, a prompt that has only ever been tried in the playground is empty
 * here too, which the empty copy says.
 */
export function LogsTab({ promptId, revisionId, revisionLabel }: LogsTabProps) {
  const { t } = useTranslation();
  const logs = usePromptLogs(promptId, revisionId);

  return (
    <section aria-label={t('lifecycle.insights.logs.viewerTitle')} className="min-w-0 overflow-hidden bg-canvas">
      <LogFilters
        source={logs.source}
        outcome={logs.outcome}
        scopeToRevision={logs.scopeToRevision}
        revisionLabel={revisionLabel}
        onSourceChange={logs.setSource}
        onOutcomeChange={logs.setOutcome}
        onScopeChange={logs.setScopeToRevision}
      />

      {logs.query.isPending ? (
        <QueryState state="loading" loadingLayout="table" />
      ) : logs.query.isError ? (
        <QueryState state="error" onRetry={() => void logs.query.refetch()} />
      ) : logs.records.length ? (
        <PromptLogTable
          records={logs.records}
          selectedId={logs.selected?.call_id}
          onSelect={logs.selectRecord}
        />
      ) : (
        <div className="grid min-h-64 place-items-center p-8 text-center text-body text-muted">
          {t('lifecycle.insights.logs.empty')}
        </div>
      )}

      <footer className="flex items-center justify-end gap-3 border-t border-border px-4 py-3">
        <Button intent="ghost" size="small" disabled={!logs.hasPrevious} onClick={logs.previousPage}>
          {t('lifecycle.insights.logs.previous')}
        </Button>
        {/* A page number and no total: the endpoint pages on a keyset and there
            is no count to show. Counting would mean a second scan of the largest
            table in the system, to render a number nobody acts on. */}
        <span className="text-caption text-muted">{t('lifecycle.insights.logs.page', { current: logs.page })}</span>
        <Button intent="ghost" size="small" disabled={!logs.hasMore} onClick={logs.nextPage}>
          {t('lifecycle.insights.logs.next')}
        </Button>
      </footer>

      <LogDetailDrawer promptId={promptId} record={logs.selected} onClose={logs.closeDetail} />
    </section>
  );
}

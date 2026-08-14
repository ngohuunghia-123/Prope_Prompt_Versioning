import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { LogDetailDrawer } from '@/features/prompt-lifecycle/components/LogDetailDrawer';
import { LogFilters } from '@/features/prompt-lifecycle/components/LogFilters';
import { PromptLogTable } from '@/features/prompt-lifecycle/components/PromptLogTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { usePromptLogs } from '@/features/prompt-lifecycle/components/usePromptLogs';

interface LogsTabProps { promptId: string; revisionId: string; }

export function LogsTab({ promptId, revisionId }: LogsTabProps) {
  const { t } = useTranslation();
  const logs = usePromptLogs(promptId, revisionId);

  if (logs.query.isPending) return <QueryState state="loading" />;
  if (logs.query.isError) return <QueryState state="error" onRetry={() => void logs.query.refetch()} />;

  return (
    <section aria-labelledby="log-viewer-title" className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
      <header className="border-b border-border px-4 py-4 sm:px-5">
        <p className="text-overline font-bold tracking-navigation-overline text-secondary uppercase">{t('lifecycle.overview.logs.eyebrow')}</p>
        <h2 id="log-viewer-title" className="mt-1 font-display text-heading-3 text-ink">{t('lifecycle.overview.logs.viewerTitle')}</h2>
      </header>
      <LogFilters
        search={logs.search}
        technology={logs.technology}
        type={logs.type}
        onSearchChange={logs.setSearch}
        onTechnologyChange={logs.setTechnology}
        onTypeChange={logs.setType}
      />
      {logs.visibleLogs.length ? (
        <PromptLogTable logs={logs.visibleLogs} selectedId={logs.selected?.id} onSelect={logs.selectLog} />
      ) : (
        <div className="grid min-h-64 place-items-center p-8 text-center text-body text-muted">{t('lifecycle.overview.logs.emptyVersion')}</div>
      )}
      <footer className="flex items-center justify-end gap-3 border-t border-border px-4 py-3">
        <Button intent="ghost" size="small" disabled={logs.currentPage === 1} onClick={logs.previousPage}>{t('lifecycle.overview.logs.previous')}</Button>
        <span className="text-caption text-muted">{t('lifecycle.overview.logs.page', { current: logs.currentPage, total: logs.pageCount })}</span>
        <Button intent="ghost" size="small" disabled={logs.currentPage === logs.pageCount} onClick={logs.nextPage}>{t('lifecycle.overview.logs.next')}</Button>
      </footer>
      <LogDetailDrawer log={logs.selected} onClose={logs.closeDetail} />
    </section>
  );
}

import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import type { LogEntry } from '@/features/prompt-lifecycle/components/logEntryTypes';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface RequestDetailModalProps {
  entry: LogEntry;
  onClose: () => void;
}

export function RequestDetailModal({ entry, onClose }: RequestDetailModalProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const { record, trace } = entry;

  return (
    <Modal
      open
      title={t('lifecycle.overview.logs.requestDetail')}
      description={t('lifecycle.overview.logs.requestIdValue', { id: record.id })}
      confirmLabel={t('lifecycle.overview.logs.close')}
      onClose={onClose}
      onConfirm={onClose}
      showCancel={false}
      className="max-w-3xl"
    >
      <div className="grid max-h-[60vh] gap-6 overflow-y-auto py-2">
        <dl className="grid gap-4 sm:grid-cols-2">
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.logs.timestamp')}</dt><dd className="mt-1 text-body text-ink">{format.date(record.timestamp)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.logs.consumer')}</dt><dd className="mt-1 text-body text-ink">{record.consumer}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.logs.version')}</dt><dd className="mt-1 text-body text-ink">{record.versionId}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.logs.latency')}</dt><dd className="mt-1 text-body text-ink">{trace ? `${format.number(trace.latencyMs)} ms` : '—'}</dd></div>
        </dl>

        {trace && Object.keys(trace.expandedVariables).length > 0 ? (
          <section>
            <h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.logs.expandedVariables')}</h4>
            <dl className="mt-2 grid gap-2 rounded-modal bg-subtle p-3 sm:grid-cols-2">
              {Object.entries(trace.expandedVariables).map(([key, value]) => <div key={key}><dt className="text-caption text-muted">{key}</dt><dd className="text-body text-ink">{value}</dd></div>)}
            </dl>
          </section>
        ) : null}

        <section><h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.logs.requestBody')}</h4><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-modal border border-border bg-subtle p-3 text-caption text-ink">{trace?.requestBody ?? '—'}</pre></section>
        <section><h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.logs.responseBody')}</h4><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-modal border border-border bg-subtle p-3 text-caption text-ink">{trace?.responseBody ?? '—'}</pre></section>

        {trace?.errorMessage ? <section className="rounded-modal border border-danger bg-danger/5 p-4"><h4 className="text-caption font-medium text-danger-text">{t('lifecycle.overview.logs.error')}</h4><p className="mt-1 text-body text-danger-text">{trace.errorMessage}</p></section> : null}

        <dl className="grid gap-4 border-t border-border pt-4 sm:grid-cols-3">
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.logs.tokens')}</dt><dd className="mt-1 text-body text-ink">{format.number(record.tokens)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.logs.cost')}</dt><dd className="mt-1 text-body text-ink">{format.currency(record.cost)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.overview.logs.outcome')}</dt><dd className={cn('mt-1 text-body font-medium', record.outcome === 'success' ? 'text-success-text' : 'text-danger-text')}>{t(`lifecycle.overview.logs.outcome${record.outcome[0]?.toUpperCase()}${record.outcome.slice(1)}`)}</dd></div>
        </dl>
      </div>
    </Modal>
  );
}

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SegmentedControl } from '@/components/SegmentedControl';
import { Tag } from '@/components/Tag';
import { Drawer } from '@/components/ui/Drawer';
import { LogTraceGraph } from '@/features/prompt-lifecycle/components/LogTraceGraph';
import type { PromptLog } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface LogDetailDrawerProps {
  log?: PromptLog;
  onClose: () => void;
}

export function LogDetailDrawer({ log, onClose }: LogDetailDrawerProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [mode, setMode] = useState<'aggregated' | 'expanded'>('aggregated');
  const metadata = log ? [
    [t('lifecycle.overview.logs.logId'), log.id],
    [t('lifecycle.overview.logs.timestamp'), format.date(log.timestamp)],
    [t('lifecycle.overview.logs.technology'), log.technology],
    [t('lifecycle.overview.logs.type'), t(`lifecycle.overview.logs.types.${log.type}`)],
    [t('lifecycle.overview.logs.model'), log.model],
    [t('lifecycle.overview.logs.status'), t(`lifecycle.overview.logs.statuses.${log.status}`)],
    [t('lifecycle.overview.logs.inputTokens'), format.number(log.inputTokens)],
    [t('lifecycle.overview.logs.outputTokens'), format.number(log.outputTokens)],
    [t('lifecycle.overview.logs.cost'), format.currency(log.cost)],
    [t('lifecycle.overview.logs.latency'), t('lifecycle.overview.logs.latencyValue', { value: format.number(log.latencyMs / 1000) })],
  ] : [];

  return (
    <Drawer open={Boolean(log)} onClose={onClose} side="right" size="wide" title={t('lifecycle.overview.logs.logDetail')}>
      {log ? (
        <div className="h-full overflow-y-auto">
          <section aria-labelledby="log-metadata-title" className="border-b border-border p-5 sm:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h3 id="log-metadata-title" className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.overview.logs.metadata')}</h3>
              <Tag state={log.status === 'success' ? 'success' : 'danger'}>{t(`lifecycle.overview.logs.statuses.${log.status}`)}</Tag>
            </div>
            <dl className="grid gap-3">
              {metadata.map(([label, value]) => <div key={label} className="grid grid-cols-3 gap-3"><dt className="text-caption text-muted">{label}</dt><dd className="col-span-2 min-w-0 break-words text-body font-medium text-ink">{value}</dd></div>)}
            </dl>
          </section>
          <section aria-labelledby="trace-title" className="p-5 sm:p-6">
            <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div><h3 id="trace-title" className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.overview.logs.traceTitle')}</h3><p className="mt-1 text-caption text-muted">{t('lifecycle.overview.logs.traceDescription')}</p></div>
              <SegmentedControl
                name="trace-view"
                label={t('lifecycle.overview.logs.traceMode')}
                value={mode}
                onValueChange={(value) => setMode(value === 'expanded' ? 'expanded' : 'aggregated')}
                options={[
                  { value: 'aggregated', label: t('lifecycle.overview.logs.aggregated') },
                  { value: 'expanded', label: t('lifecycle.overview.logs.expanded') },
                ]}
                className="shrink-0 sm:max-w-64"
              />
            </div>
            <LogTraceGraph mode={mode} />
          </section>
        </div>
      ) : null}
    </Drawer>
  );
}

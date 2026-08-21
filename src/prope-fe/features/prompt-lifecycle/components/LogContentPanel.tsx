import { useTranslation } from 'react-i18next';

import { Tag } from '@/components/Tag';
import { INTERNAL_APP_LABEL } from '@/features/workspace/keyTypes';
import { appLabel, type CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface LogContentPanelProps {
  record: CallRecord;
}

export function LogContentPanel({ record }: LogContentPanelProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();
  const rows: Array<[string, string]> = [
    [t('lifecycle.insights.logs.callId'), record.call_id],
    [t('lifecycle.insights.logs.columns.time'), format.dateTime(record.created_at)],
    [t('lifecycle.insights.logs.source'), t(`lifecycle.insights.sources.${record.source}`)],
    [t('lifecycle.insights.logs.columns.app'), appLabel(record, INTERNAL_APP_LABEL)],
    [t('lifecycle.insights.logs.versionId'), record.version_id ?? '—'],
    [t('lifecycle.insights.logs.columns.revision'), record.revision_number === null ? '—' : `r${record.revision_number}`],
    [t('lifecycle.insights.logs.columns.model'), record.upstream_model ?? '—'],
    [t('lifecycle.insights.logs.inputTokens'), record.input_tokens === null ? '—' : format.number(record.input_tokens)],
    [t('lifecycle.insights.logs.outputTokens'), record.output_tokens === null ? '—' : format.number(record.output_tokens)],
    [t('lifecycle.insights.logs.columns.cost'), format.callCost(record.cost, record.currency, record.cost_status)],
    [t('lifecycle.insights.logs.upstreamLatency'), format.duration(record.upstream_duration_ms)],
    [t('lifecycle.insights.logs.addedLatency'), format.duration(record.added_latency_ms)],
    [t('lifecycle.insights.logs.streaming'), t(record.streaming ? 'common.yes' : 'common.no')],
    [t('lifecycle.insights.logs.pinned'), t(record.pinned ? 'common.yes' : 'common.no')],
    ...(record.error_class ? [[t('lifecycle.insights.logs.errorClass'), record.error_class] as [string, string]] : []),
  ];

  return (
    <section className="grid gap-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-overline font-bold uppercase tracking-navigation-overline text-muted">{t('lifecycle.insights.logs.metadata')}</h3>
        <Tag state={record.outcome === 'ok' ? 'success' : 'danger'}>{t(`lifecycle.insights.outcomes.${record.outcome}`)}</Tag>
      </div>
      <dl className="grid gap-3">
        {rows.map(([term, value]) => (
          <div key={term} className="grid grid-cols-3 gap-3">
            <dt className="text-caption text-muted">{term}</dt>
            <dd className="col-span-2 min-w-0 break-words text-body font-medium text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

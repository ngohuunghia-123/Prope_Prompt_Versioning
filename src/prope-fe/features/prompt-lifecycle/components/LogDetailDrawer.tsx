import { useTranslation } from 'react-i18next';

import { Drawer } from '@/components/ui/Drawer';
import { Tag } from '@/components/Tag';
import { INTERNAL_APP_LABEL } from '@/features/workspace/keyTypes';
import { appLabel, type CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface LogDetailDrawerProps {
  record?: CallRecord;
  onClose: () => void;
}

/**
 * One call's metadata, and there is nothing else to show.
 *
 * **The trace graph that used to live here is gone.** It took no data — it was a
 * fixed drawing — and the only thing that could have made it real is the request
 * and response text, which ADR-0018 forbids a read path for and
 * `tests/security/test_no_body_read_path.py` asserts is unreachable. A drawing
 * of a trace on a screen that cannot obtain one is a promise the system does not
 * keep.
 *
 * What is left is every column the ledger does hold, including the two the table
 * has no room for: `error_class`, which is the only thing that says *why* a call
 * failed, and the latency split, which says whether the time went upstream or
 * into Prope.
 */
export function LogDetailDrawer({ record, onClose }: LogDetailDrawerProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  const rows: Array<[string, string]> = record
    ? [
        [t('lifecycle.insights.logs.callId'), record.call_id],
        [t('lifecycle.insights.logs.columns.time'), format.dateTime(record.created_at)],
        [t('lifecycle.insights.logs.source'), t(`lifecycle.insights.sources.${record.source}`)],
        [t('lifecycle.insights.logs.columns.app'), appLabel(record, INTERNAL_APP_LABEL)],
        [t('lifecycle.insights.logs.versionId'), record.version_id ?? '—'],
        [
          t('lifecycle.insights.logs.columns.revision'),
          record.revision_number === null ? '—' : `r${record.revision_number}`,
        ],
        [t('lifecycle.insights.logs.columns.model'), record.upstream_model ?? '—'],
        [t('lifecycle.insights.logs.inputTokens'), record.input_tokens === null ? '—' : format.number(record.input_tokens)],
        [t('lifecycle.insights.logs.outputTokens'), record.output_tokens === null ? '—' : format.number(record.output_tokens)],
        [t('lifecycle.insights.logs.columns.cost'), format.callCost(record.cost, record.currency, record.cost_status)],
        [t('lifecycle.insights.logs.upstreamLatency'), format.duration(record.upstream_duration_ms)],
        [t('lifecycle.insights.logs.addedLatency'), format.duration(record.added_latency_ms)],
        [t('lifecycle.insights.logs.streaming'), t(record.streaming ? 'common.yes' : 'common.no')],
        [t('lifecycle.insights.logs.pinned'), t(record.pinned ? 'common.yes' : 'common.no')],
        ...(record.error_class ? [[t('lifecycle.insights.logs.errorClass'), record.error_class] as [string, string]] : []),
      ]
    : [];

  return (
    <Drawer open={Boolean(record)} onClose={onClose} side="right" size="wide" title={t('lifecycle.insights.logs.logDetail')}>
      {record ? (
        <div className="h-full overflow-y-auto p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-overline font-bold tracking-navigation-overline text-muted uppercase">
              {t('lifecycle.insights.logs.metadata')}
            </h3>
            <Tag state={record.outcome === 'ok' ? 'success' : 'danger'}>
              {t(`lifecycle.insights.outcomes.${record.outcome}`)}
            </Tag>
          </div>
          <dl className="grid gap-3">
            {rows.map(([term, value]) => (
              <div key={term} className="grid grid-cols-3 gap-3">
                <dt className="text-caption text-muted">{term}</dt>
                <dd className="col-span-2 min-w-0 break-words text-body font-medium text-ink">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-6 text-caption text-muted">{t('lifecycle.insights.logs.noBodyNote')}</p>
        </div>
      ) : null}
    </Drawer>
  );
}

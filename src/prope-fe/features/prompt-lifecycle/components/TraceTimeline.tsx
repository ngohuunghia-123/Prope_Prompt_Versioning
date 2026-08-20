import { CheckCircle, WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';

import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import type { TraceDetail } from '@/features/prompt-lifecycle/traceTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';
import { cn } from '@/lib/cn';

interface TraceTimelineProps {
  trace: TraceDetail;
}

export function TraceTimeline({ trace }: TraceTimelineProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  return (
    <section aria-label={t('lifecycle.insights.trace.traceTitle')} className="grid gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-heading-3 text-ink">
            {t('lifecycle.insights.trace.traceTitle')}
          </h3>
          <p className="mt-1 font-mono text-caption text-muted">{trace.trace_id}</p>
        </div>
        <div className="flex items-center gap-2">
          <Tag state="neutral">Langfuse</Tag>
          <StatusBadge tone={trace.status === 'success' ? 'active' : 'error'}>
            {t(`lifecycle.insights.trace.status.${trace.status}`)}
          </StatusBadge>
        </div>
      </header>

      <dl className="grid grid-cols-2 gap-3 rounded-xl border border-border bg-canvas p-3 text-caption sm:grid-cols-3">
        <div>
          <dt className="text-muted">{t('lifecycle.insights.trace.duration')}</dt>
          <dd className="mt-1 font-semibold text-ink">{format.duration(trace.duration_ms)}</dd>
        </div>
        <div>
          <dt className="text-muted">{t('lifecycle.insights.trace.provider')}</dt>
          <dd className="mt-1 font-semibold text-ink">Langfuse</dd>
        </div>
        <div>
          <dt className="text-muted">{t('lifecycle.insights.trace.spans')}</dt>
          <dd className="mt-1 font-semibold text-ink">{format.number(trace.spans.length)}</dd>
        </div>
      </dl>

      <ol className="grid list-none gap-2 p-0">
        {trace.spans.map((span) => {
          const width = Math.max((span.duration_ms / Math.max(trace.duration_ms, 1)) * 100, 3);
          return (
            <li
              key={span.span_id}
              className={cn(
                'grid gap-2 rounded-xl border border-border bg-surface p-3 shadow-inset',
                span.parent_span_id && 'ml-5',
              )}
            >
              <div className="flex min-w-0 items-center gap-2">
                {span.status === 'success' ? (
                  <CheckCircle aria-hidden weight="fill" className="size-4 shrink-0 text-success-text" />
                ) : (
                  <WarningCircle aria-hidden weight="fill" className="size-4 shrink-0 text-danger-text" />
                )}
                <span className="min-w-0 flex-1 truncate font-mono text-caption font-semibold text-ink">
                  {span.name}
                </span>
                <span className="shrink-0 text-caption tabular-nums text-muted">
                  {format.duration(span.duration_ms)}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-subtle">
                <span
                  aria-hidden
                  className={cn('block h-full rounded-full', span.status === 'success' ? 'bg-secondary' : 'bg-danger')}
                  style={{ width: `${width}%` }}
                />
              </div>
              {span.model ? (
                <p className="text-caption text-muted">
                  {span.model}
                  {span.input_tokens !== null || span.output_tokens !== null
                    ? ` · ${format.number(span.input_tokens ?? 0)} / ${format.number(span.output_tokens ?? 0)}`
                    : null}
                </p>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

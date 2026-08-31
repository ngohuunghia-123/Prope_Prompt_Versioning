import { useTranslation } from 'react-i18next';

import { Tag } from '@/components/Tag';
import type { CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import type { TraceMessage } from '@/features/prompt-lifecycle/traceTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';
import { cn } from '@/lib/cn';

interface RequestConversationProps {
  messages: TraceMessage[];
  /** The row the drawer was opened from, for the figures under the panels. */
  record: CallRecord;
}

/**
 * The id the server gives the one message it synthesises from the response body
 * (`prompt_registry/observability.py`). Everything else in the array is
 * `request-{n}` — a turn that was *sent*. Splitting on the id rather than on
 * `role === 'assistant'` matters: a few-shot prompt sends assistant turns as
 * input, and a role test would file them under the model's answer.
 */
const RESPONSE_ID = 'response';

function MessageList({ messages, empty }: { messages: TraceMessage[]; empty: string }) {
  const { t } = useTranslation();
  if (messages.length === 0) {
    return <p className="rounded-xl border border-dashed border-border p-4 text-caption text-muted">{empty}</p>;
  }
  return (
    <ol className="grid list-none gap-3 p-0">
      {messages.map((message) => (
        <li key={message.message_id} className="grid gap-1">
          <div className="flex items-center gap-2">
            <span className="text-overline font-bold uppercase tracking-navigation-overline text-muted">
              {t(`lifecycle.insights.trace.roles.${message.role}`)}
            </span>
            {/* Said per message, not once per call: a reader comparing an
                output against the prompt that produced it needs to know which
                of the two the redactor touched. */}
            {message.redacted ? <Tag state="warning">{t('lifecycle.insights.trace.redacted')}</Tag> : null}
          </div>
          <p
            className={cn(
              'overflow-x-auto whitespace-pre-wrap break-words rounded-xl border border-border bg-canvas px-4 py-3 text-body text-ink',
              message.role === 'system' && 'border-dashed text-muted',
            )}
          >
            {message.content}
          </p>
        </li>
      ))}
    </ol>
  );
}

/**
 * What was sent and what came back, side by side.
 *
 * Previously one flat chronological list, in which the model's answer was the
 * last bubble of a conversation and looked like another turn somebody typed.
 * Reading a log is a comparison — *this* input produced *that* output — and the
 * two columns are what make it one glance instead of a scroll. The figures sit
 * under both because they are properties of the pair, not of either side.
 */
export function RequestConversation({ messages, record }: RequestConversationProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();
  const input = messages.filter((message) => message.message_id !== RESPONSE_ID);
  const output = messages.filter((message) => message.message_id === RESPONSE_ID);

  const figures: Array<[string, string]> = [
    [t('lifecycle.insights.logs.columns.model'), record.upstream_model ?? '—'],
    [
      t('lifecycle.insights.logs.columns.tokens'),
      record.usage_status === 'unknown'
        ? t('lifecycle.insights.usageUnknown')
        : t('lifecycle.insights.trace.tokenPair', {
            input: format.number(record.input_tokens ?? 0),
            output: format.number(record.output_tokens ?? 0),
          }),
    ],
    [t('lifecycle.insights.logs.columns.cost'), format.callCost(record.cost, record.currency, record.cost_status)],
    [t('lifecycle.insights.logs.upstreamLatency'), format.duration(record.upstream_duration_ms)],
  ];

  return (
    <section aria-label={t('lifecycle.insights.trace.requestTitle')} className="grid gap-4">
      <header>
        <h3 className="font-display text-heading-3 text-ink">{t('lifecycle.insights.trace.requestTitle')}</h3>
        <p className="mt-1 text-caption text-muted">{t('lifecycle.insights.trace.requestDescription')}</p>
      </header>

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <section className="grid min-w-0 content-start gap-2">
          <h4 className="text-overline font-bold uppercase tracking-navigation-overline text-muted">
            {t('lifecycle.insights.trace.input')}
          </h4>
          <MessageList messages={input} empty={t('lifecycle.insights.trace.noInput')} />
        </section>
        <section className="grid min-w-0 content-start gap-2">
          <h4 className="text-overline font-bold uppercase tracking-navigation-overline text-muted">
            {t('lifecycle.insights.trace.output')}
          </h4>
          <MessageList messages={output} empty={t('lifecycle.insights.trace.noOutput')} />
        </section>
      </div>

      <dl className="grid gap-3 rounded-xl border border-border bg-subtle p-4 sm:grid-cols-4">
        {figures.map(([term, value]) => (
          <div key={term} className="grid min-w-0 gap-1">
            <dt className="text-caption text-muted">{term}</dt>
            <dd className="min-w-0 break-words text-body font-medium text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

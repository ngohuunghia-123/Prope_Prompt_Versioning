import { ArrowDown, ArrowUp, Coins, Timer } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import type { TrialTotals } from '@/features/prompt-lifecycle/components/useTrialChat';
import type { TrialUsage } from '@/features/prompt-lifecycle/trialApi';

interface PlaygroundMeterProps {
  /** The turn that just finished, or nothing before the first one lands. */
  usage?: TrialUsage;
  totals: TrialTotals;
  streaming: boolean;
  /** Characters received on the turn in flight — the one figure that moves live. */
  received: number;
}

/**
 * What this conversation has cost so far.
 *
 * **Tokens arrive once per turn, at the end, because that is when the provider
 * reports them.** An OpenAI-compatible stream carries usage in a trailing chunk
 * and nowhere else, so a token counter that ticked upward mid-answer would be an
 * invention. What moves during a turn is the character count, labelled as one;
 * the moment the trailer lands it is replaced by the provider's own figures and
 * the session totals step up. Nothing here is estimated from text length.
 *
 * **An unpriced turn shows as unpriced and never as zero.** `cost` is `null` when
 * the workspace has no price row for the `(provider, model)` pair that ran, which
 * is a real and common state — a model tried from the settings panel before
 * anybody has entered its rate card. Rendering that as `$0.00` would be the one
 * mistake the ledger's own pricing module refuses to make (`ck_call_record_cost_
 * is_never_zero`), so it is refused here too.
 */
export function PlaygroundMeter({ usage, totals, streaming, received }: PlaygroundMeterProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language;

  const money = (value: number, currency: string | null) => {
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: currency ?? 'USD',
        minimumFractionDigits: 6,
        maximumFractionDigits: 6,
      }).format(value);
    } catch {
      // A currency code Intl does not know — the price table takes free text, so
      // this is reachable. Showing the figure beside the raw code beats throwing
      // inside a render.
      return `${value.toFixed(6)} ${currency ?? ''}`.trim();
    }
  };

  const count = (value: number) => new Intl.NumberFormat(locale).format(value);

  return (
    <Card title={t('lifecycle.playground.meter.title')} description={t('lifecycle.playground.meter.description')}>
      <div className="grid grid-cols-2 gap-3">
        <Figure
          icon={<ArrowUp aria-hidden className="size-4 text-muted" />}
          label={t('lifecycle.playground.meter.inputTokens')}
          value={usage?.inputTokens == null ? '—' : count(usage.inputTokens)}
        />
        <Figure
          icon={<ArrowDown aria-hidden className="size-4 text-muted" />}
          label={t('lifecycle.playground.meter.outputTokens')}
          value={
            streaming
              ? t('lifecycle.playground.meter.receiving', { count: received })
              : usage?.outputTokens == null
                ? '—'
                : count(usage.outputTokens)
          }
        />
        <Figure
          icon={<Coins aria-hidden className="size-4 text-muted" />}
          label={t('lifecycle.playground.meter.turnCost')}
          value={
            usage === undefined
              ? '—'
              : usage.cost === null
                ? t('lifecycle.playground.meter.unpriced')
                : money(Number(usage.cost), usage.currency)
          }
        />
        <Figure
          icon={<Timer aria-hidden className="size-4 text-muted" />}
          label={t('lifecycle.playground.meter.latency')}
          value={
            usage?.upstreamDurationMs == null
              ? '—'
              : t('lifecycle.playground.meter.milliseconds', { count: usage.upstreamDurationMs })
          }
        />
      </div>

      <dl className="grid gap-2 rounded-modal border border-border bg-subtle p-4">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-caption text-muted">{t('lifecycle.playground.meter.sessionTurns')}</dt>
          <dd className="text-body font-medium text-ink">{count(totals.turns)}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-caption text-muted">{t('lifecycle.playground.meter.sessionTokens')}</dt>
          <dd className="text-body font-medium text-ink">
            {t('lifecycle.playground.meter.tokenSplit', {
              input: count(totals.inputTokens),
              output: count(totals.outputTokens),
            })}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-caption text-muted">{t('lifecycle.playground.meter.sessionCost')}</dt>
          <dd className="text-body font-medium text-ink">
            {totals.cost === null ? t('lifecycle.playground.meter.unpriced') : money(totals.cost, totals.currency)}
          </dd>
        </div>
      </dl>

      {totals.unpricedTurns > 0 ? (
        <p className="text-caption text-muted">
          {t('lifecycle.playground.meter.unpricedTurns', { count: totals.unpricedTurns })}
        </p>
      ) : null}
      <p className="text-caption text-muted">{t('lifecycle.playground.meter.ledgerNote')}</p>
    </Card>
  );
}

function Figure({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="grid gap-1 rounded-modal border border-border bg-surface p-3">
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-caption text-muted">{label}</span>
      </div>
      <span className="truncate text-body font-medium text-ink">{value}</span>
    </div>
  );
}

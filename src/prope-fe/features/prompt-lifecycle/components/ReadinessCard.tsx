import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Textarea } from '@/components/ui';
import { Tag } from '@/components/Tag';
import { cn } from '@/lib/cn';
import type { Finding, ReadinessCard as ReadinessCardData } from '@/features/prompt-lifecycle/readinessTypes';

/**
 * The readiness card. **Counts first, rows second.**
 *
 * That ordering is the card's whole layout argument. A person arriving at a
 * fresh import wants *"9 registered, 6 have no suite, 1 declares all three risk
 * legs"* before they want nine rows — and the counts come from the server, so two
 * clients cannot disagree about the headline.
 *
 * **Every sentence on this card comes from the `vi` catalogue, keyed by
 * `rule_id`** (ADR-0053). The server sends a code and numbers; CI fails the build
 * on a rule with no key. The single exception is a finding's `evidence` line,
 * which the server generates directly in Vietnamese and has already passed
 * through its redaction rail before storing — it is rendered as **plain text**
 * here and never as markdown or HTML, which is the client half of that
 * guarantee.
 *
 * **Nothing on this card blocks anything** (ADR-0067 §4). There is no button
 * that stops a submit, no severity above `warning`, and no state in which the
 * card refuses. It is a panel, and the moment it grows a gate it stops being one.
 *
 * **The trifecta finding cannot be dismissed away.** It is the one finding that
 * outranks everything else, so the server keeps rendering it in full even when
 * somebody dismissed it last time, and the dismiss control is hidden here to
 * match. One click should not be able to permanently silence the highest-signal
 * thing this feature can say.
 */

export interface ReadinessCardProps {
  card: ReadinessCardData;
  onDismiss?: (ruleId: string, reason: string) => Promise<void> | void;
  onStartProbe?: () => Promise<void> | void;
  probeBusy?: boolean;
  className?: string;
}

const TRIFECTA = 'lethal_trifecta';

export function ReadinessCard({
  card,
  onDismiss,
  onStartProbe,
  probeBusy = false,
  className,
}: ReadinessCardProps) {
  const { t } = useTranslation();
  const [showDismissed, setShowDismissed] = useState(false);

  const visible = card.findings.filter((finding) => showDismissed || !finding.dismissed);

  return (
    <section className={cn('space-y-4 rounded-xl border border-border bg-surface p-4 shadow-panel', className)}>
      <header className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-heading-3 text-ink">{t('readiness.card.title')}</h3>
          <Tag state={card.frozen ? 'neutral' : 'default'}>
            {card.frozen ? t('readiness.card.frozen') : t('readiness.card.live')}
          </Tag>
        </div>

        {/* Counts first. */}
        <div className="flex flex-wrap items-center gap-2">
          {card.warning_count > 0 ? (
            <Tag state="warning">{t('readiness.card.warnings', { count: card.warning_count })}</Tag>
          ) : null}
          {card.advice_count > 0 ? (
            <Tag state="neutral">{t('readiness.card.advice', { count: card.advice_count })}</Tag>
          ) : null}
          {card.dismissed_count > 0 ? (
            <button
              type="button"
              className="text-caption text-muted underline underline-offset-2"
              onClick={() => setShowDismissed((shown) => !shown)}
            >
              {showDismissed ? t('readiness.card.hideDismissed') : t('readiness.card.showDismissed')}
              {` (${card.dismissed_count})`}
            </button>
          ) : null}
        </div>

        {card.frozen ? (
          <p className="text-caption text-muted">{t('readiness.card.frozenHint')}</p>
        ) : null}
        {card.lane_b_unavailable ? (
          <p className="text-caption text-muted">{t('readiness.card.laneBUnavailable')}</p>
        ) : null}
      </header>

      {visible.length === 0 ? (
        <p className="text-body text-muted">{t('readiness.card.empty')}</p>
      ) : (
        <ul className="space-y-3">
          {visible.map((finding) => (
            <FindingRow
              key={finding.rule_id}
              finding={finding}
              onDismiss={
                finding.rule_id === TRIFECTA || card.frozen || !onDismiss ? undefined : onDismiss
              }
            />
          ))}
        </ul>
      )}

      <ProbeSection card={card} onStartProbe={onStartProbe} busy={probeBusy} />

      <footer className="text-caption text-muted">
        {t('readiness.card.catalogueVersion', { version: card.catalogue_version })}
      </footer>
    </section>
  );
}

function FindingRow({
  finding,
  onDismiss,
}: {
  finding: Finding;
  onDismiss?: (ruleId: string, reason: string) => Promise<void> | void;
}) {
  const { t } = useTranslation();
  const [dismissing, setDismissing] = useState(false);
  const [reason, setReason] = useState('');

  const key = `readiness.rule.${finding.rule_id}`;

  return (
    <li
      className={cn(
        'rounded-lg border border-border p-3',
        finding.dismissed ? 'opacity-60' : null,
        finding.severity === 'warning' ? 'border-warning-strong' : null,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium text-ink">{t(`${key}.title`)}</p>
        <Tag state={finding.severity === 'warning' ? 'warning' : 'neutral'}>
          {t(`readiness.severity.${finding.severity}`)}
        </Tag>
      </div>

      {/* The sentence, from the catalogue, with the server's numbers in it. */}
      <p className="mt-1 text-body text-muted">{t(`${key}.body`, finding.params)}</p>

      {/*
        Why am I being told this. On the row rather than in a legend, because a
        reader's first question about an unwelcome finding is exactly this, and
        the answer has to travel with the thing that provoked it.
      */}
      <p className="mt-1 text-caption text-muted">
        {t(`readiness.admitted.${finding.admitted_by}`, {
          defaultValue: t('readiness.admitted.always'),
        })}
      </p>

      {/*
        The one generated line. PLAIN TEXT — never markdown, never HTML. The
        server strips links, tags and credential shapes before storing it; this
        renderer being unable to follow a link is the other half of that.
      */}
      {finding.evidence ? (
        <p className="mt-2 rounded bg-subtle px-2 py-1 text-caption text-ink">
          <span className="text-muted">{t('readiness.card.evidenceLabel')}: </span>
          {finding.evidence}
        </p>
      ) : null}

      {finding.dismissed && finding.dismissal_reason ? (
        <p className="mt-2 text-caption text-muted">
          {t('readiness.card.dismissedBecause', { reason: finding.dismissal_reason })}
        </p>
      ) : null}

      {onDismiss && !finding.dismissed ? (
        <div className="mt-2">
          {dismissing ? (
            <div className="space-y-2">
              <Textarea
                label={t('readiness.card.dismissReason')}
                placeholder={t('readiness.card.dismissReasonPlaceholder')}
                value={reason}
                rows={2}
                onChange={(event) => setReason(event.target.value)}
              />
              <p className="text-caption text-muted">{t('readiness.card.dismissReasonRequired')}</p>
              <div className="flex gap-2">
                <Button
                  size="small"
                  intent="secondary"
                  disabled={!reason.trim()}
                  onClick={() => {
                    void onDismiss(finding.rule_id, reason.trim());
                    setDismissing(false);
                  }}
                >
                  {t('readiness.card.dismiss')}
                </Button>
                <Button size="small" intent="ghost" onClick={() => setDismissing(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          ) : (
            <Button size="small" intent="ghost" onClick={() => setDismissing(true)}>
              {t('readiness.card.dismiss')}
            </Button>
          )}
        </div>
      ) : null}
    </li>
  );
}

/**
 * The probe offer, and what it is about to spend.
 *
 * The set ids are printed before the button rather than after the bill, because
 * this is the one control on the card that costs the workspace money and A-164
 * fixes what it runs — so what it runs can be shown in advance and will still be
 * true when it runs.
 */
function ProbeSection({
  card,
  onStartProbe,
  busy,
}: {
  card: ReadinessCardData;
  onStartProbe?: () => Promise<void> | void;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const probe = card.probe;
  const total = probe ? probe.refused_count + probe.leaked_count + probe.error_count : 0;

  return (
    <section className="space-y-2 rounded-lg border border-border bg-subtle p-3">
      <p className="font-medium text-ink">{t('readiness.probe.title')}</p>
      <p className="text-caption text-muted">{t('readiness.probe.description')}</p>

      {probe ? (
        <div className="space-y-1">
          <p className="text-body text-ink">
            {t('readiness.probe.result', { refused: probe.refused_count, total })}
          </p>
          <div className="flex flex-wrap gap-2">
            <Tag state="success">{`${t('readiness.probe.refused')}: ${probe.refused_count}`}</Tag>
            {probe.leaked_count > 0 ? (
              <Tag state="danger">{`${t('readiness.probe.leaked')}: ${probe.leaked_count}`}</Tag>
            ) : null}
            {probe.error_count > 0 ? (
              <Tag state="neutral">{`${t('readiness.probe.errors')}: ${probe.error_count}`}</Tag>
            ) : null}
          </div>
          {/* An error is not a pass. Said out loud so the number is not misread. */}
          {probe.error_count > 0 ? (
            <p className="text-caption text-muted">{t('readiness.probe.errorsHint')}</p>
          ) : null}
        </div>
      ) : null}

      {card.probe_offers.length === 0 ? (
        <p className="text-caption text-muted">{t('readiness.probe.noSets')}</p>
      ) : (
        <>
          <p className="text-caption text-muted">
            {t('readiness.probe.willRun', { sets: card.probe_offers.join(', ') })}
          </p>
          <p className="text-caption text-muted">{t('readiness.probe.cost')}</p>
          {onStartProbe ? (
            <Button size="small" intent="secondary" disabled={busy} onClick={() => void onStartProbe()}>
              {busy ? t('readiness.probe.running') : t('readiness.probe.start')}
            </Button>
          ) : null}
        </>
      )}
    </section>
  );
}

import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Textarea } from '@/components/ui/Textarea';
import { GateResult } from '@/features/prompt-lifecycle/components/ImprovementFindingList';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import type { ImprovementFinding, ProposalDetail } from '@/features/prompt-lifecycle/improvementTypes';

interface PropaiFindingDrawerProps {
  finding?: ImprovementFinding;
  /** The revision currently selected in the rail — the "before" side of the diff. */
  currentBody: string;
  busy: boolean;
  /** ADR-0070: the detail read, for an llm_edit's rationale + rails report. */
  detail?: ProposalDetail;
  onClose: () => void;
  onAccept: (proposalId: string) => void;
  onDismissProposal: (proposalId: string, reason: string) => void;
  onDismissFinding: (findingId: string, reason: string) => void;
}

/** ~4 characters per token is the usual rough estimate for mixed-language text. */
const CHARS_PER_TOKEN = 4;

function estimateTokens(body: string): number {
  return Math.ceil(body.length / CHARS_PER_TOKEN);
}

/**
 * The right sidebar behind a PropAI suggestion card.
 *
 * Before/after by block, an estimated token footprint, and the two acts —
 * open the editor prefilled with the candidate (nothing is written until that
 * separate save), or dismiss with a reason. The estimate is labelled as an
 * estimate everywhere it appears; it is a sizing hint, not a ledger figure.
 */
export function PropaiFindingDrawer({ finding, currentBody, busy, detail, onClose, onAccept, onDismissProposal, onDismissFinding }: PropaiFindingDrawerProps) {
  const { t } = useTranslation();
  const [reason, setReason] = useState('');
  const [dismissing, setDismissing] = useState(false);
  const candidate = finding?.proposal?.candidate_body ?? null;
  const close = () => {
    setReason('');
    setDismissing(false);
    onClose();
  };
  const submitDismissal = () => {
    if (!finding || !reason.trim()) return;
    if (finding.proposal) onDismissProposal(finding.proposal.proposal_id, reason.trim());
    else onDismissFinding(finding.finding_id, reason.trim());
    close();
  };

  return (
    <Drawer open={Boolean(finding)} onClose={close} side="right" size="wide" title={t('lifecycle.surface.monitoring.propai.detailTitle')}>
      {finding ? (
        <div className="grid h-full min-h-0 content-start gap-5 overflow-y-auto p-5">
          <section className="rounded-modal border border-border bg-surface p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className={finding.severity === 'warning' ? 'text-overline font-bold uppercase tracking-wide text-danger' : 'text-overline font-bold uppercase tracking-wide text-muted'}>
                {finding.severity === 'warning'
                  ? t('lifecycle.surface.monitoring.propai.urgent')
                  : t(`improvement.severity.${finding.severity}`)}
              </span>
              <h2 className="font-display text-heading-3 text-ink">{t(`improvement.detector.${finding.detector_id}.title`)}</h2>
            </div>
            <p className="mt-2 text-caption font-medium uppercase tracking-wide text-muted">{t('lifecycle.surface.monitoring.propai.why')}</p>
            <p className="text-body text-muted">{t(`improvement.detector.${finding.detector_id}.body`, { ...finding.params })}</p>
            {finding.evidence_line ? (
              <>
                <p className="mt-3 text-caption font-medium uppercase tracking-wide text-muted">{t('lifecycle.surface.monitoring.propai.rootCause')}</p>
                <p className="text-body text-ink">{finding.evidence_line}</p>
              </>
            ) : null}
          </section>

          {finding.proposal ? (
            <section className="rounded-modal border border-border bg-surface p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Tag>{t(`improvement.kind.${finding.proposal.remedy_kind}`)}</Tag>
                {finding.proposal.remedy_family ? (
                  <span className="text-body font-semibold text-ink">{t(`improvement.family.${finding.proposal.remedy_family}.title`)}</span>
                ) : null}
              </div>
              <GateResult proposal={finding.proposal} />
              {candidate !== null ? (
                <>
                  <div className="mt-4">
                    <h3 className="font-display text-heading-3 text-ink">{t('lifecycle.surface.monitoring.propai.compareTitle')}</h3>
                    <p className="mt-1 text-caption text-muted">
                      {t('lifecycle.surface.monitoring.propai.compareHint', {
                        input: estimateTokens(currentBody),
                        output: estimateTokens(candidate),
                      })}
                    </p>
                  </div>
                  <div className="mt-3">
                    <PromptBlockAccordion beforeBody={currentBody} body={candidate} sideBySide />
                  </div>
                </>
              ) : (
                <p className="mt-3 text-body text-muted">{t('lifecycle.surface.monitoring.propai.noPreviewHint')}</p>
              )}
              {/*
                ADR-0070 §5, the demotion rendered: the model's rationale is a
                collapsed, machine-attributed note BESIDE the evidence — it is
                a claim about the edit, never the card, and never a substitute
                for the diff above it.
              */}
              {finding.proposal.remedy_family === 'llm_edit' && detail?.draft_rationale ? (
                <details className="mt-3 rounded-md border border-border bg-surface-subtle p-3">
                  <summary className="cursor-pointer text-caption font-medium text-fg">
                    {t('improvement.proposal.rationaleTitle')}
                  </summary>
                  <p className="mt-2 text-body text-muted">{detail.draft_rationale}</p>
                </details>
              ) : null}
              {detail?.rails_report ? (
                <details className="mt-2 rounded-md border border-border bg-surface-subtle p-3">
                  <summary className="cursor-pointer text-caption font-medium text-fg">
                    {t('improvement.proposal.railsTitle')}
                  </summary>
                  <p className="mt-2 text-caption text-muted">
                    {t('improvement.proposal.railsPassed', { attempts: detail.rails_report.attempts.length })}
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {detail.rails_report.attempts
                      .filter((attempt) => attempt.code !== 'passed')
                      .map((attempt) => (
                        <li key={attempt.attempt} className="text-caption text-muted">
                          {t('improvement.proposal.railsAttempt', { attempt: attempt.attempt, code: attempt.code })}
                        </li>
                      ))}
                  </ul>
                </details>
              ) : null}
            </section>
          ) : (
            <p className="text-body text-muted">{t('lifecycle.surface.monitoring.propai.noProposalHint')}</p>
          )}

          {!dismissing ? (
            <div className="flex flex-wrap gap-2">
              {finding.proposal && candidate !== null ? (
                <Button type="button" size="small" disabled={busy} onClick={() => onAccept(finding.proposal!.proposal_id)}>
                  {t('improvement.proposal.accept')}
                </Button>
              ) : null}
              <Button type="button" intent="ghost" size="small" disabled={busy} onClick={() => setDismissing(true)}>
                {t('improvement.inbox.dismiss')}
              </Button>
            </div>
          ) : (
            <div className="grid gap-2 rounded-modal border border-border bg-surface p-4">
              <Textarea
                label={t('improvement.inbox.dismissReason')}
                placeholder={t('improvement.inbox.dismissReasonPlaceholder')}
                value={reason}
                rows={2}
                onChange={(event) => setReason(event.target.value)}
              />
              {/* A rate without reasons cannot tell a bad detector from a bad remedy. */}
              <p className="text-xs text-muted">{t('improvement.inbox.dismissReasonRequired')}</p>
              <div className="flex gap-2">
                <Button type="button" intent="secondary" size="small" disabled={!reason.trim() || busy} onClick={submitDismissal}>
                  {t('improvement.inbox.dismiss')}
                </Button>
                <Button type="button" intent="ghost" size="small" onClick={() => setDismissing(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          )}
          {!dismissing && finding.proposal && candidate !== null ? (
            <p className="-mt-3 text-xs text-muted">{t('improvement.proposal.acceptHint')}</p>
          ) : null}
        </div>
      ) : null}
    </Drawer>
  );
}

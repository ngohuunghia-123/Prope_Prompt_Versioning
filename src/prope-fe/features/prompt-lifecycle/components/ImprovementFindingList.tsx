import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Button, Textarea } from '@/components/ui';
import { Tag } from '@/components/Tag';
import { cn } from '@/lib/cn';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type {
  ImprovementFinding,
  ImprovementProposal,
} from '@/features/prompt-lifecycle/improvementTypes';

/**
 * The findings list. Shared by the inbox and the per-prompt tab.
 *
 * **An occurrence count, never a repeated row.** A signal that has fired every
 * day for a fortnight is one row saying *"seen 14 times"*, because the dedupe
 * index in `improvement.finding` made it one row. Fourteen items would be deck 6
 * slide 64's alert fatigue produced by the data model rather than by the render.
 *
 * **Every sentence comes from the `vi` catalogue, keyed by `detector_id`**
 * (ADR-0053). The server sends a code and numbers; CI fails the build on a
 * detector with no key. The single exception is `evidence_line`, which the server
 * generates directly in Vietnamese and has already passed its redaction rail
 * **before storage** — it renders as plain text here and never as markdown or
 * HTML, which is the client half of that guarantee.
 *
 * **A proposal renders its gate result and no rationale** (ADR-0068 §4). What a
 * reviewer sees is the per-case eval delta and the honest limit underneath it;
 * what they do not see is the model's story about why its own edit works, because
 * that story does not describe the edit's behaviour and showing it asks them to
 * trust an unreliable narrative on top of an unvalidated judgement.
 *
 * **Accepting writes nothing** (SR-6). The button opens an editor prefilled with
 * the candidate body, and the copy under it says so, because a person who thinks
 * they have applied a change when they have not is the worst outcome this screen
 * can produce.
 */

interface ImprovementFindingListProps {
  findings: ImprovementFinding[];
  onDismissFinding: (findingId: string, reason: string) => Promise<void> | void;
  onAcceptProposal: (proposalId: string) => Promise<void> | void;
  onDismissProposal: (proposalId: string, reason: string) => Promise<void> | void;
  /** The inbox shows which prompt each finding is about; the per-prompt tab does not. */
  showPromptId?: boolean;
  busy?: boolean;
}

export function GateResult({ proposal }: { proposal: ImprovementProposal }) {
  const { t } = useTranslation();
  const delta = proposal.gate_delta;
  if (!delta) return null;

  return (
    <div className="mt-3 rounded-md border border-border bg-surface-subtle p-3">
      <p className="text-xs font-medium text-fg">{t('improvement.proposal.gateTitle')}</p>
      {/*
        The precondition, before the numbers. A reader who does not know that a
        failing candidate is discarded rather than shown greyed out cannot read
        the delta correctly — they would take "passed" as the interesting fact
        rather than as the entry requirement.
      */}
      <p className="mt-1 text-xs text-fg-muted">{t('improvement.proposal.gateHint')}</p>
      <p className="mt-1 text-sm text-fg">
        {t('improvement.proposal.gateSummary', {
          candidate: delta.candidate_pass,
          baseline: delta.baseline_pass,
          total: delta.case_count,
        })}
      </p>
      <ul className="mt-2 space-y-1">
        {delta.cases.map((entry) => (
          <li key={entry.case_id} className="flex items-center justify-between gap-3 text-xs">
            <span className="truncate text-fg-muted">{entry.name}</span>
            <span className="shrink-0 tabular-nums text-fg-muted">
              {t('improvement.proposal.caseBaseline')} {entry.baseline ?? '—'} ·{' '}
              {t('improvement.proposal.caseCandidate')} {entry.candidate}
            </span>
          </li>
        ))}
      </ul>
      {/*
        The honest limit, on the screen and not only in the ADR. "Did not regress
        on this suite" is exactly as strong as the suite, and a passing gate read
        as an endorsement is how this whole design fails.
      */}
      <p className="mt-2 text-xs text-fg-muted">{t('improvement.proposal.gateLimit')}</p>
    </div>
  );
}

function ProposalBlock({
  proposal,
  onAccept,
  onDismiss,
  busy,
}: {
  proposal: ImprovementProposal;
  onAccept: () => void;
  onDismiss: (reason: string) => void;
  busy?: boolean;
}) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [reason, setReason] = useState('');
  const [refusing, setRefusing] = useState(false);

  return (
    <div className="mt-3 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Tag>{t(`improvement.kind.${proposal.remedy_kind}`)}</Tag>
        {proposal.remedy_family ? (
          <span className="text-sm font-medium text-fg">
            {t(`improvement.family.${proposal.remedy_family}.title`)}
          </span>
        ) : null}
        {/*
          A proposal has a deadline and expiring is a recorded disposition —
          `improvement_proposal_expired`, written with `actor_type='system'`.
          Leaving the date off the card meant a reviewer could come back to find
          the row gone and no indication it had ever been on a clock.
        */}
        <span className="text-xs text-fg-muted">
          {t('improvement.proposal.expiresAt', { when: format.date(proposal.expires_at) })}
        </span>
      </div>
      {proposal.remedy_family ? (
        <p className="mt-1 text-sm text-fg-muted">
          {t(`improvement.family.${proposal.remedy_family}.body`)}
        </p>
      ) : (
        <p className="mt-1 text-sm text-fg-muted">{t('improvement.proposal.noBody')}</p>
      )}

      <GateResult proposal={proposal} />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="small" onClick={onAccept} disabled={busy}>
          {t('improvement.proposal.accept')}
        </Button>
        <Button size="small" intent="ghost" onClick={() => setRefusing((open) => !open)}>
          {t('improvement.proposal.dismiss')}
        </Button>
      </div>
      {/* Nothing has changed yet, and the copy says so under the button. */}
      <p className="mt-1 text-xs text-fg-muted">{t('improvement.proposal.acceptHint')}</p>

      {refusing ? (
        <div className="mt-2 space-y-2">
          <Textarea
            label={t('improvement.inbox.dismissReason')}
            placeholder={t('improvement.inbox.dismissReasonPlaceholder')}
            value={reason}
            rows={2}
            onChange={(event) => setReason(event.target.value)}
          />
          <p className="text-xs text-fg-muted">{t('improvement.inbox.dismissReasonRequired')}</p>
          <Button
            size="small"
            intent="secondary"
            disabled={!reason.trim() || busy}
            onClick={() => {
              onDismiss(reason.trim());
              setReason('');
              setRefusing(false);
            }}
          >
            {t('improvement.proposal.dismiss')}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function ImprovementFindingList({
  findings,
  onDismissFinding,
  onAcceptProposal,
  onDismissProposal,
  showPromptId = false,
  busy = false,
}: ImprovementFindingListProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const [dismissing, setDismissing] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  return (
    <ul className="divide-y divide-border">
      {findings.map((finding) => (
        <li key={finding.finding_id} className="p-4 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Tag
                  className={cn(
                    finding.severity === 'warning' ? 'text-warning' : 'text-fg-muted',
                  )}
                >
                  {t(`improvement.severity.${finding.severity}`)}
                </Tag>
                <span className="text-sm font-medium text-fg">
                  {t(`improvement.detector.${finding.detector_id}.title`)}
                </span>
              </div>
              <p className="mt-1 text-sm text-fg-muted">
                {t(`improvement.detector.${finding.detector_id}.body`, {
                  ...finding.params,
                })}
              </p>
              {/*
                The one sentence the triage model wrote. Plain text, always — the
                rail stripped links and tags before storage, and the renderer
                being unable to follow one is the other half of that.
              */}
              {finding.evidence_line ? (
                <p className="mt-1 text-sm text-fg">{finding.evidence_line}</p>
              ) : null}
              {/*
                An occurrence count is not a signal on its own: fourteen times in
                two days and fourteen times in a quarter argue for opposite
                actions, and the wire has carried `first_seen` and `last_seen`
                the whole time. The window is what makes the count readable.

                On the inbox — the one view that spans prompts — the prompt is a
                LINK and not a printed `prm_…`. An id somebody has to copy out and
                paste into a search box is a queue that ends without an action,
                which is the shape this module's own lock refuses.
              */}
              <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-muted">
                <span>{t('improvement.inbox.occurrences', { count: finding.occurrence_count })}</span>
                <span aria-hidden>·</span>
                <span>{t('improvement.inbox.firstSeen', { when: format.date(finding.first_seen) })}</span>
                <span aria-hidden>·</span>
                <span>{t('improvement.inbox.lastSeen', { when: format.date(finding.last_seen) })}</span>
                {showPromptId ? (
                  <>
                    <span aria-hidden>·</span>
                    <Link
                      to={`/app/prompts/${encodeURIComponent(finding.prompt_id)}`}
                      className="rounded-lg font-medium text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus"
                    >
                      {t('improvement.inbox.openPrompt')}
                    </Link>
                  </>
                ) : null}
              </p>
            </div>
            <Button
              size="small"
              intent="ghost"
              onClick={() =>
                setDismissing((open) => (open === finding.finding_id ? null : finding.finding_id))
              }
            >
              {t('improvement.inbox.dismiss')}
            </Button>
          </div>

          {finding.proposal ? (
            <ProposalBlock
              proposal={finding.proposal}
              busy={busy}
              onAccept={() => void onAcceptProposal(finding.proposal!.proposal_id)}
              onDismiss={(text) => void onDismissProposal(finding.proposal!.proposal_id, text)}
            />
          ) : null}

          {dismissing === finding.finding_id ? (
            <div className="mt-3 space-y-2">
              <Textarea
                label={t('improvement.inbox.dismissReason')}
                placeholder={t('improvement.inbox.dismissReasonPlaceholder')}
                value={reason}
                rows={2}
                onChange={(event) => setReason(event.target.value)}
              />
              {/* A rate without reasons cannot tell a bad detector from a bad
                  remedy, which argue for opposite fixes (OQ-157). */}
              <p className="text-xs text-fg-muted">
                {t('improvement.inbox.dismissReasonRequired')}
              </p>
              <Button
                size="small"
                intent="secondary"
                disabled={!reason.trim() || busy}
                onClick={() => {
                  void onDismissFinding(finding.finding_id, reason.trim());
                  setReason('');
                  setDismissing(null);
                }}
              >
                {t('improvement.inbox.dismiss')}
              </Button>
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

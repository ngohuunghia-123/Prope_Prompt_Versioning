import { Check, X } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { reviewScreenOptions, useReviewDecisionMutation } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { useWorkspaceId } from '@/features/prompt-lifecycle/useWorkspaceId';

/**
 * The reviewer's one screen: the diff, the eval evidence, the cost delta, and a
 * recorded decision.
 *
 * It is a single `GET /prompts/{id}/revisions/{versionId}/review`, which is the
 * whole point of that endpoint — the alternative is a screen that assembles a
 * decision from five reads and can show a diff from one moment beside an eval
 * result from another.
 *
 * **Two of the four non-negotiables are visible here.** Only an `Approved`
 * revision may ever be released, and self-approval is *recorded, never refused* —
 * so `self_authored` renders as a notice rather than as a disabled button.
 */
export function ReviewDetailPage() {
  const { t } = useTranslation();
  const { promptId, versionId } = useParams();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const workspaceId = useWorkspaceId();
  const query = useQuery({
    ...reviewScreenOptions(promptId ?? '', versionId ?? ''),
    enabled: Boolean(promptId && versionId),
  });
  const mutation = useReviewDecisionMutation(workspaceId);
  const [decision, setDecision] = useState<'approve' | 'changes' | null>(null);
  const [comment, setComment] = useState('');

  if (!promptId || !versionId) return <QueryState state="empty" />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const screen = query.data;
  const summary = screen.summary;
  const passed = summary?.suites.reduce((total, suite) => total + suite.pass_count, 0) ?? 0;
  const cases = summary?.suites.reduce((total, suite) => total + suite.case_count, 0) ?? 0;
  const delta = summary?.total_cost_delta ?? null;

  const decide = () => {
    if (!decision) return;
    mutation.mutate(
      {
        promptId,
        versionId,
        decision,
        comment: comment.trim() || undefined,
        // ADR-0005. A failing suite does not block approval; it requires the
        // approver to write down why they are approving anyway, and that reason is
        // stored on the approval. The server tells the screen when it is required.
        acknowledgementReason:
          decision === 'approve' && screen.acknowledgement_required ? comment.trim() : undefined,
      },
      {
        onSuccess: () =>
          void navigate(decision === 'approve' ? `/app/releases/${promptId}/${versionId}` : '/app/reviews'),
      },
    );
  };

  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={`${t('status.inReview')} · r${screen.revision.revision_number}`}
        title={screen.model_name}
        description={screen.revision.change_summary}
      />

      {screen.self_authored ? (
        // Recorded, never refused — one of the four non-negotiables. The approval
        // row carries `self_approved`, and this is the reviewer being told so.
        <div role="note" className="rounded-xl border border-warning-strong bg-warning p-4 text-body text-ink">
          {t('lifecycle.review.selfAuthored')}
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <MetricTile
          label={t('lifecycle.review.eval')}
          value={screen.summary_available ? `${passed}/${cases}` : '—'}
          detail={t(screen.summary_available ? 'lifecycle.review.deterministic' : 'lifecycle.review.noEvidence')}
        />
        <MetricTile
          label={t('lifecycle.review.candidateCost')}
          value={format.currency(delta?.candidate, delta?.currency ?? undefined)}
        />
        <MetricTile
          label={t('lifecycle.review.costDelta')}
          value={format.currency(delta?.absolute, delta?.currency ?? undefined)}
          detail={t('lifecycle.review.warningOnly')}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title={t('lifecycle.review.releasedRevision')}>
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-subtle p-4 font-sans text-body text-ink">
            {screen.diff ? screen.diff.lines.filter((line) => line.op !== 'add').map((line) => line.text).join('\n') : t('lifecycle.review.noBaseline')}
          </pre>
        </Card>
        <Card className="relative overflow-hidden animate-navigation-panel motion-reduce:animate-none" title={t('lifecycle.review.candidateRevision')}>
          <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-warning" />
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-warning-strong bg-warning p-4 font-sans text-body text-ink">
            {screen.diff ? screen.diff.lines.filter((line) => line.op !== 'remove').map((line) => line.text).join('\n') : t('lifecycle.review.noBaseline')}
          </pre>
        </Card>
      </div>

      <Card title={t('lifecycle.review.evidence')}>
        <div className="mt-3 grid gap-3">
          {summary && summary.suites.length > 0 ? (
            summary.suites.map((suite) => (
              <div key={suite.run_id} className="flex items-center justify-between gap-4 rounded-lg border border-border bg-subtle p-3">
                <span className="text-ink">{suite.suite_name} · v{suite.suite_version}</span>
                <Tag state={suite.fail_count + suite.error_count > 0 ? 'warning' : 'success'}>
                  {suite.pass_count}/{suite.case_count}
                </Tag>
              </div>
            ))
          ) : (
            <p className="text-body text-muted">{t('lifecycle.review.noEvidence')}</p>
          )}
        </div>
      </Card>

      {screen.approvals.length > 0 ? (
        <Card title={t('lifecycle.review.decisions')}>
          <ul className="mt-3 grid gap-2">
            {screen.approvals.map((approval) => (
              <li key={approval.approval_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-subtle p-3 text-body">
                <span className="text-ink">{approval.decision}{approval.self_approved ? ` · ${t('lifecycle.review.selfApproved')}` : ''}</span>
                <span className="text-caption text-muted">{format.date(approval.decided_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {mutation.isError ? (
        <div role="alert" className="rounded-xl border border-danger-strong bg-danger p-4 text-body text-ink">
          {t('lifecycle.states.error.title')}
        </div>
      ) : null}

      <div className="flex flex-wrap justify-end gap-3">
        <Button type="button" intent="neutral" leadingIcon={<X aria-hidden className="size-4" />} onClick={() => setDecision('changes')}>{t('lifecycle.review.requestChanges')}</Button>
        <Button type="button" intent="success" leadingIcon={<Check aria-hidden className="size-4" />} onClick={() => setDecision('approve')}>{t('lifecycle.review.approve')}</Button>
      </div>

      <Modal
        open={decision !== null}
        title={t(decision === 'approve' ? 'lifecycle.review.approveTitle' : 'lifecycle.review.changesTitle')}
        description={t(decision === 'approve' ? 'lifecycle.review.approveDescription' : 'lifecycle.review.changesDescription')}
        confirmLabel={t('common.confirm')}
        destructive={decision === 'changes'}
        onClose={() => { setDecision(null); setComment(''); }}
        onConfirm={decide}
      >
        {/* `request-changes` requires a comment; approving a revision whose evals
            failed requires an acknowledgement reason (ADR-0005). Both are the same
            box, because to the reviewer they are the same act: say why. */}
        <Textarea
          className="min-h-24"
          label={t(decision === 'changes' || screen.acknowledgement_required ? 'lifecycle.review.reasonRequired' : 'lifecycle.review.comment')}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
      </Modal>
    </div>
  );
}

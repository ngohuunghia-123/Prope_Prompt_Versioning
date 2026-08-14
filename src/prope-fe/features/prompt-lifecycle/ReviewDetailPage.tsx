import { ArrowRight, Check, X } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { HelpIcon } from '@/components/ui/HelpIcon';
import { Modal } from '@/components/ui/Modal';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { reviewOptions, useReviewDecisionMutation } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface DiffLine { type: 'added' | 'removed' | 'unchanged'; text: string; }

function computeDiff(before: string, after: string): DiffLine[] {
  const beforeLines = before.split('\n');
  const afterLines = after.split('\n');
  const maxLen = Math.max(beforeLines.length, afterLines.length);
  const result: DiffLine[] = [];
  for (let i = 0; i < maxLen; i++) {
    const b = beforeLines[i] ?? null;
    const a = afterLines[i] ?? null;
    if (a === b) {
      if (b !== null) result.push({ type: 'unchanged', text: b });
    } else {
      if (b !== null) result.push({ type: 'removed', text: b });
      if (a !== null) result.push({ type: 'added', text: a });
    }
  }
  return result;
}

function PromptDiffPanel() {
  const { t } = useTranslation();
  const diff = computeDiff(
    `<system>\nYou are the support triage assistant.\nReturn the priority and recommended queue.\n</system>`,
    `<system>\nYou are the support triage assistant.\nEscalate sensitive refunds and validate the output against the approved JSON schema.\n</system>`,
  );
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card title={t('lifecycle.review.releasedRevision')}>
        <pre className="mt-3 whitespace-pre-wrap rounded-lg border border-border bg-subtle p-4 font-sans text-body text-ink">{diff.filter((l) => l.type !== 'added').map((l) => l.text).join('\n')}</pre>
      </Card>
      <Card className="relative overflow-hidden" title={t('lifecycle.review.candidateRevision')}>
        <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-warning" />
        <pre className="mt-3 whitespace-pre-wrap rounded-lg border border-warning-strong bg-warning p-4 font-sans text-body text-ink">{diff.filter((l) => l.type !== 'removed').map((l) => l.text).join('\n')}</pre>
      </Card>
    </div>
  );
}

export function ReviewDetailPage() {
  const { t } = useTranslation();
  const { reviewId } = useParams();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const reviewQueryOptions = reviewOptions(reviewId ?? '');
  const query = useQuery({ ...reviewQueryOptions, enabled: !!reviewId });
  const mutation = useReviewDecisionMutation();
  const [decision, setDecision] = useState<'approve' | 'changes' | null>(null);
  if (!reviewId) return <QueryState state="error" titleOverride={t('lifecycle.review.notFoundTitle')} descriptionOverride={t('lifecycle.review.notFoundBody')} />;
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  const review = query.data;
  if (!review) return <QueryState state="empty" />;
  const decide = () => {
    if (!decision) return;
    mutation.mutate(
      { reviewId: review.id, decision },
      {
        onSuccess: () => {
          if (decision === 'approve') {
            void navigate(`/app/releases/${review.promptId}`);
          } else {
            void navigate(`/app/prompts/${review.promptId}/edit`);
          }
        },
      },
    );
  };
  return (
    <div className="grid gap-6">
      <PageIntro eyebrow={`${t('lifecycle.status.inReview')} · ${review.revision}`} title={review.promptTitle} description={review.summary} />
      <div className="grid gap-4 sm:grid-cols-3">
        <MetricTile label={t('lifecycle.review.eval')} value={`${review.passed}/${review.total}`} detail={t('lifecycle.review.deterministic')} />
        <MetricTile label={t('lifecycle.review.candidateCost')} value={format.currency(review.candidateCost)} />
        <MetricTile label={t('lifecycle.review.costDelta')} value={`+${format.percent((review.candidateCost - review.releasedCost) / review.releasedCost)}`} detail={t('lifecycle.review.warningOnly')} />
      </div>

      <div className="flex items-center gap-3">
        <h3 className="font-display text-heading-3 text-ink">{t('lifecycle.review.promptChanges')}</h3>
        <HelpIcon title={t('lifecycle.help.review.promptChanges')}>
          <p>{t('lifecycle.help.review.promptChanges')}</p>
        </HelpIcon>
      </div>
      <PromptDiffPanel />

      <div className="flex items-center gap-3">
        <h3 className="font-display text-heading-3 text-ink">{t('lifecycle.review.evaluationSummary')}</h3>
        <HelpIcon title={t('lifecycle.help.review.evaluationSummary')}>
          <p>{t('lifecycle.help.review.evaluationSummary')}</p>
        </HelpIcon>
      </div>
      <Card title={t('lifecycle.review.evidence')}>
        <div className="mt-3 grid gap-3">
          {(['schema', 'sensitive', 'forbidden'] as const).map((item) => (
            <div key={item} className="flex items-center justify-between gap-4 rounded-lg border border-border bg-subtle p-3">
              <span className="text-ink">{t(`lifecycle.review.assertions.${item}`)}</span>
              <Tag state={item === 'forbidden' ? 'warning' : 'success'}>
                {t(item === 'forbidden' ? 'lifecycle.review.warning' : 'lifecycle.review.pass')}
              </Tag>
            </div>
          ))}
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <h3 className="font-display text-heading-3 text-ink">{t('lifecycle.review.decision')}</h3>
        <HelpIcon title={t('lifecycle.help.review.decision')}>
          <p>{t('lifecycle.help.review.decision')}</p>
        </HelpIcon>
      </div>
      <div className="flex flex-wrap justify-end gap-3">
        <Button type="button" intent="neutral" leadingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={() => void navigate(`/app/prompts/${review.promptId}/playground`)}>
          {t('lifecycle.review.goToEval')}
        </Button>
        <Button type="button" intent="neutral" leadingIcon={<X aria-hidden className="size-4" />} onClick={() => setDecision('changes')}>{t('lifecycle.review.requestChanges')}</Button>
        <Button type="button" intent="success" leadingIcon={<Check aria-hidden className="size-4" />} onClick={() => setDecision('approve')}>{t('lifecycle.review.approve')}</Button>
      </div>
      <Modal
        open={decision !== null}
        title={t(decision === 'approve' ? 'lifecycle.review.approveTitle' : 'lifecycle.review.changesTitle')}
        description={t(decision === 'approve' ? 'lifecycle.review.approveDescription' : 'lifecycle.review.changesDescription')}
        confirmLabel={t('common.confirm')}
        destructive={decision === 'changes'}
        onClose={() => setDecision(null)}
        onConfirm={decide}
      />
    </div>
  );
}

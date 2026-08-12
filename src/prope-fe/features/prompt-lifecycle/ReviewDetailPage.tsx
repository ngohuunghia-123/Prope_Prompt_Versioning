import { Check, X } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { reviewOptions, useReviewDecisionMutation } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

export function ReviewDetailPage() {
  const { t } = useTranslation();
  const { reviewId } = useParams();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const query = useQuery(reviewOptions(reviewId ?? 'review-support-r8'));
  const mutation = useReviewDecisionMutation();
  const [decision, setDecision] = useState<'approve' | 'changes' | null>(null);
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  const review = query.data;
  if (!review) return <QueryState state="empty" />;
  const decide = () => {
    if (!decision) return;
    mutation.mutate({ reviewId: review.id, decision }, { onSuccess: () => void navigate(decision === 'approve' ? '/app/releases/rev_support_8' : '/app/reviews') });
  };
  return (
    <div className="grid gap-6">
      <PageIntro eyebrow={`${t('status.inReview')} · ${review.revision}`} title={review.promptTitle} description={review.summary} />
      <div className="grid gap-4 sm:grid-cols-3"><MetricTile label={t('lifecycle.review.eval')} value={`${review.passed}/${review.total}`} detail={t('lifecycle.review.deterministic')} /><MetricTile label={t('lifecycle.review.candidateCost')} value={format.currency(review.candidateCost)} /><MetricTile label={t('lifecycle.review.costDelta')} value={`+${format.percent((review.candidateCost - review.releasedCost) / review.releasedCost)}`} detail={t('lifecycle.review.warningOnly')} /></div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title={t('lifecycle.review.releasedRevision')}><pre className="mt-3 whitespace-pre-wrap rounded-lg border border-border bg-subtle p-4 font-sans text-body text-ink">You are a support triage assistant.{`\n`}Return the priority and recommended queue.</pre></Card>
        <Card className="relative overflow-hidden animate-navigation-panel motion-reduce:animate-none" title={t('lifecycle.review.candidateRevision')}><span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-warning" /><pre className="mt-3 whitespace-pre-wrap rounded-lg border border-warning-strong bg-warning p-4 font-sans text-body text-ink">You are a support triage assistant.{`\n`}Escalate sensitive refunds.{`\n`}Return JSON matching the approved schema.</pre></Card>
      </div>
      <Card title={t('lifecycle.review.evidence')}><div className="mt-3 grid gap-3">{['schema', 'sensitive', 'forbidden'].map((item) => <div key={item} className="flex items-center justify-between gap-4 rounded-lg border border-border bg-subtle p-3"><span className="text-ink">{t(`lifecycle.review.assertions.${item}`)}</span><Tag state={item === 'forbidden' ? 'warning' : 'success'}>{t(item === 'forbidden' ? 'lifecycle.review.warning' : 'lifecycle.review.pass')}</Tag></div>)}</div></Card>
      <div className="flex flex-wrap justify-end gap-3"><Button type="button" intent="neutral" leadingIcon={<X aria-hidden className="size-4" />} onClick={() => setDecision('changes')}>{t('lifecycle.review.requestChanges')}</Button><Button type="button" intent="success" leadingIcon={<Check aria-hidden className="size-4" />} onClick={() => setDecision('approve')}>{t('lifecycle.review.approve')}</Button></div>
      <Modal open={decision !== null} title={t(decision === 'approve' ? 'lifecycle.review.approveTitle' : 'lifecycle.review.changesTitle')} description={t(decision === 'approve' ? 'lifecycle.review.approveDescription' : 'lifecycle.review.changesDescription')} confirmLabel={t('common.confirm')} destructive={decision === 'changes'} onClose={() => setDecision(null)} onConfirm={decide} />
    </div>
  );
}

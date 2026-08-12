import { ArrowRight, CheckSquare } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { reviewsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { useWorkspaceId } from '@/features/prompt-lifecycle/useWorkspaceId';

export function ReviewQueuePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const workspaceId = useWorkspaceId();
  const query = useQuery({ ...reviewsOptions(workspaceId), enabled: Boolean(workspaceId) });
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (query.data.length === 0) return <QueryState state="empty" />;
  return (
    <div className="grid gap-6">
      <PageIntro eyebrow={t('lifecycle.reviews.eyebrow')} title={t('lifecycle.reviews.title')} description={t('lifecycle.reviews.description')} />
      <div className="grid gap-4 sm:grid-cols-3"><MetricTile label={t('lifecycle.reviews.pending')} value={format.number(query.data.length)} /><MetricTile label={t('lifecycle.reviews.median')} value={t('lifecycle.reviews.medianValue')} /><MetricTile label={t('lifecycle.reviews.target')} value={t('lifecycle.reviews.targetValue')} /></div>
      <div className="grid gap-4">
        {query.data.map((review) => (
          <article key={review.id} className="grid gap-4 rounded-modal border border-border bg-surface p-5 shadow-panel lg:grid-cols-[1fr_auto] lg:items-center">
            <div><p className="flex items-center gap-2 text-caption font-semibold text-warning-strong"><CheckSquare aria-hidden className="size-4" />{t('status.inReview')} · {review.revision}</p><h3 className="mt-2 font-display text-heading-3 text-ink">{review.promptTitle}</h3><p className="mt-2 text-body text-muted">{review.summary}</p><p className="mt-3 text-caption text-muted">{review.owner} · {format.date(review.submittedAt)}</p></div>
            {/* Eval counts and the cost delta are **per revision** and live on the
                review screen, not on the task. Fetching one review screen per row
                would be a fan-out on the queue; the numbers appear the moment the
                reviewer opens the task, which is when a decision is being made. */}
            <div className="flex flex-wrap items-center gap-4 lg:justify-end"><div><p className="text-caption text-muted">{t('lifecycle.reviews.due')}</p><strong className={`text-body-large ${review.overdue ? 'text-warning-strong' : 'text-ink'}`}>{t(review.overdue ? 'lifecycle.reviews.overdue' : 'lifecycle.reviews.onTime')}</strong></div><Button type="button" trailingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={() => void navigate(`/app/reviews/${review.promptId}/${review.versionId}`)}>{t('lifecycle.reviews.open')}</Button></div>
          </article>
        ))}
      </div>
    </div>
  );
}

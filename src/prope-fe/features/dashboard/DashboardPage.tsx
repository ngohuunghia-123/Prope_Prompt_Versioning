import {
  CheckCircle,
  Clock,
  ClockCounterClockwise,
  Stack,
  Warning,
  WarningCircle,
} from '@phosphor-icons/react';
import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import {
  foldersOptions,
  improvementInboxOptions,
  promptsOptions,
  workspaceStatsOptions,
} from '@/features/prompt-lifecycle/queries';
import { openReviewTasksOptions } from '@/features/notifications/queries';
import type { ReviewTask } from '@/features/prompt-lifecycle/releaseTypes';
import type { ImprovementFinding } from '@/features/prompt-lifecycle/improvementTypes';
import { PROMPT_RECENTS_CHANGED, readRecentPromptsList, type RecentPrompt } from '@/components/promptRecentOpensStorage';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

/**
 * Tổng quan không gian (`/app/home`).
 *
 * **Mỗi số trên trang đến từ một endpoint trả sẵn** — không có tổng hợp mới:
 * stats và folder counts là những request sidebar/grid đã mount sẵn, review
 * tasks đếm bằng độ dài mảng server đã lọc `status=open`, findings lấy các cột
 * đếm server tính xong (`warning_count`). Một khối lỗi chỉ làm hỏng khối của nó;
 * phần còn lại của trang vẫn đọc được.
 */

type TileTone = 'default' | 'success' | 'warning' | 'info';

interface TileProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  tone?: TileTone;
  /** Điều hướng tới một route khi bấm thẻ. */
  href?: string;
  /** Cuộn tới một khối trên chính trang này (thẻ "Chờ duyệt" → hàng chờ bên dưới). */
  scrollToId?: string;
}

function Tile({ icon, label, value, sub, tone = 'default', href, scrollToId }: TileProps) {
  const surfaceClass = {
    default: 'bg-surface',
    success: 'bg-success/10',
    warning: 'bg-warning/10',
    info: 'bg-info/10',
  }[tone];
  const accentClass = {
    default: 'text-secondary',
    success: 'text-success-strong',
    warning: 'text-warning-strong',
    info: 'text-info-strong',
  }[tone];

  const body = (
    <div
      className={`flex min-h-32 flex-col gap-2 rounded-modal border border-border p-5 shadow-panel transition-colors ${(href || scrollToId) ? 'hover:border-secondary' : ''} ${surfaceClass}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-caption text-muted">{label}</span>
        <div className={`flex size-9 items-center justify-center rounded-lg bg-subtle/50 ${accentClass}`}>
          {icon}
        </div>
      </div>
      <span className={`font-display text-heading-1 font-semibold ${accentClass === 'text-secondary' ? 'text-ink' : accentClass}`}>
        {value}
      </span>
      {sub ? <span className="text-caption text-muted">{sub}</span> : null}
    </div>
  );

  if (href) {
    return (
      <Link
        to={href}
        className="rounded-modal focus-visible:outline-2 focus-visible:outline-focus"
      >
        {body}
      </Link>
    );
  }
  if (scrollToId) {
    return (
      <button
        type="button"
        onClick={() => document.getElementById(scrollToId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
        className="cursor-pointer rounded-modal text-left focus-visible:outline-2 focus-visible:outline-focus"
      >
        {body}
      </button>
    );
  }
  return body;
}

/** Trạng thái chờ của một thẻ: giữ khung thẻ, chỉ thay nội dung bằng shimmer. */
function TileLoading() {
  return (
    <div className="flex min-h-32 flex-col gap-3 rounded-modal border border-border bg-surface p-5 shadow-panel" aria-hidden>
      <Skeleton variant="line" className="w-24" />
      <Skeleton variant="line" className="h-7 w-14" />
    </div>
  );
}

/** Thẻ lỗi riêng lẻ — nút thử lại nằm trong thẻ, các thẻ khác không bị kéo theo. */
function TileError({ label, onRetry }: { label: string; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-32 flex-col items-start justify-between gap-3 rounded-modal border border-border bg-surface p-5 shadow-panel">
      <span className="flex items-center gap-1.5 text-caption text-muted">
        <WarningCircle aria-hidden className="size-4 text-secondary" />
        {label}
      </span>
      <Button type="button" intent="neutral" onClick={onRetry}>
        {t('common.tryAgain')}
      </Button>
    </div>
  );
}

function TotalPromptsTile() {
  const { t } = useTranslation();
  const query = useQuery(workspaceStatsOptions);
  const label = t('dashboard.tiles.totalPrompts');
  if (query.isPending) return <TileLoading />;
  if (query.isError) return <TileError label={label} onRetry={() => void query.refetch()} />;
  return (
    <Tile
      icon={<Stack aria-hidden className="size-5" weight="duotone" />}
      label={label}
      value={new Intl.NumberFormat('vi-VN').format(query.data.totalPrompts)}
      sub={t('dashboard.tiles.approvedPercent', { percent: `${query.data.qualityPercent.toFixed(1)}%` })}
    />
  );
}

/**
 * Tổng `approved_count` mà `/api/v1/folders` đã tính bằng SQL — con số này nằm
 * sẵn trong cache vì sidebar cũng đọc cùng danh sách.
 */
function ApprovedTile() {
  const { t } = useTranslation();
  const { number } = useLocaleFormatters();
  const query = useQuery(foldersOptions);
  const label = t('dashboard.tiles.approved');
  if (query.isPending) return <TileLoading />;
  if (query.isError) return <TileError label={label} onRetry={() => void query.refetch()} />;
  const approved = query.data.reduce((sum, folder) => sum + folder.approvedCount, 0);
  return (
    <Tile
      icon={<CheckCircle aria-hidden className="size-5" weight="duotone" />}
      label={label}
      value={number(approved)}
      tone="success"
      href="/app/prompts"
    />
  );
}

function PendingReviewsTile() {
  const { t } = useTranslation();
  const { number } = useLocaleFormatters();
  const query = useQuery(openReviewTasksOptions());
  const label = t('dashboard.tiles.pendingReviews');
  if (query.isPending) return <TileLoading />;
  if (query.isError) return <TileError label={label} onRetry={() => void query.refetch()} />;
  // Cờ `overdue` đi trên từng row — không cần request thứ hai để tách nó ra.
  const overdue = query.data.filter((task) => task.overdue).length;
  return (
    <Tile
      icon={<ClockCounterClockwise aria-hidden className="size-5" weight="duotone" />}
      label={label}
      value={number(query.data.length)}
      sub={overdue > 0 ? t('dashboard.tiles.pendingOverdueSub', { count: overdue }) : undefined}
      tone="warning"
      scrollToId="dashboard-review-queue"
    />
  );
}

function FindingsTile() {
  const { t } = useTranslation();
  const { number } = useLocaleFormatters();
  const query = useQuery(improvementInboxOptions);
  const label = t('dashboard.tiles.findings');
  if (query.isPending) return <TileLoading />;
  if (query.isError) return <TileError label={label} onRetry={() => void query.refetch()} />;
  return (
    <Tile
      icon={<Warning aria-hidden className="size-5" weight="duotone" />}
      label={label}
      value={number(query.data.warning_count)}
      sub={t('improvement.inbox.advice', { count: query.data.advice_count })}
      tone="info"
      href="/app/improvement"
    />
  );
}

function reviewHref(task: ReviewTask): string {
  // Cùng đích với `ReviewTaskRedirect`: tab Monitor & Improve của đúng revision đang chờ.
  return `/app/prompts/${encodeURIComponent(task.prompt_id)}?tab=monitoring&version=${encodeURIComponent(task.version_id)}`;
}

function ReviewQueueCard({ titles }: { titles: Map<string, string> }) {
  const { t } = useTranslation();
  const query = useQuery(openReviewTasksOptions());

  let content: React.ReactNode;
  if (query.isError) {
    content = <QueryState state="error" onRetry={() => void query.refetch()} />;
  } else if (query.isPending) {
    content = (
      <div className="grid gap-2" aria-hidden>
        <Skeleton variant="line" />
        <Skeleton variant="line" />
        <Skeleton variant="line" />
      </div>
    );
  } else if (query.data.length === 0) {
    content = (
      <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
        <CheckCircle aria-hidden className="size-8 text-success-strong" weight="duotone" />
        <p className="max-w-prose text-body text-muted">{t('dashboard.queue.empty')}</p>
      </div>
    );
  } else {
    const tasks = [...query.data]
      .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
      .slice(0, 5);
    content = (
      <ul className="grid divide-y divide-border">
        {tasks.map((task) => (
          <li key={task.review_task_id} className="-mx-1">
            <Link
              to={reviewHref(task)}
              className="flex items-center gap-3 rounded-lg px-1 py-2 transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
            >
              <ClockCounterClockwise aria-hidden className="size-5 shrink-0 text-secondary" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-body font-medium text-ink">
                  {titles.get(task.prompt_id) ?? task.prompt_id}
                </span>
                <span className="block truncate text-caption text-muted">
                  {t(`navigation.advanced.updates.kinds.${task.kind}`)} · {task.version_id}
                </span>
              </span>
              {task.overdue ? <StatusBadge tone="error">{t('dashboard.queue.overdue')}</StatusBadge> : null}
            </Link>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <Card title={t('dashboard.queue.title')} description={t('dashboard.queue.description')}>
      {content}
    </Card>
  );
}

/**
 * localStorage, không gọi API — cùng nguồn với danh sách trong nav
 * (`PromptRecentOpens`), chỉ khác cách trình bày.
 */
function RecentPromptsCard() {
  const { t } = useTranslation();
  const { date } = useLocaleFormatters();
  const [recent, setRecent] = useState<RecentPrompt[]>([]);

  useEffect(() => {
    const sync = () => setRecent(readRecentPromptsList());
    sync();
    window.addEventListener(PROMPT_RECENTS_CHANGED, sync);
    return () => window.removeEventListener(PROMPT_RECENTS_CHANGED, sync);
  }, []);

  let content: React.ReactNode;
  if (recent.length === 0) {
    content = (
      <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
        <Clock aria-hidden className="size-8 text-muted" weight="duotone" />
        <p className="max-w-prose text-body text-muted">{t('navigation.advanced.home.recentPromptsEmpty')}</p>
      </div>
    );
  } else {
    content = (
      <ul className="grid divide-y divide-border">
        {recent.map((prompt) => (
          <li key={prompt.id} className="-mx-1">
            <Link
              to={`/app/prompts/${prompt.id}`}
              className="flex items-center gap-3 rounded-lg px-1 py-2 transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
            >
              <Clock aria-hidden className="size-5 shrink-0 text-muted" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-body font-medium text-ink">{prompt.title}</span>
                <span className="block text-caption text-muted">{t('dashboard.recent.visitedAt', { when: date(prompt.visitedAt) })}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <Card title={t('dashboard.recent.title')} description={t('dashboard.recent.description')}>
      {content}
    </Card>
  );
}

function FindingsCard({ titles }: { titles: Map<string, string> }) {
  const { t } = useTranslation();
  const query = useQuery(improvementInboxOptions);

  let content: React.ReactNode;
  if (query.isError) {
    content = <QueryState state="error" onRetry={() => void query.refetch()} />;
  } else if (query.isPending) {
    content = (
      <div className="grid gap-2" aria-hidden>
        <Skeleton variant="line" />
        <Skeleton variant="line" />
        <Skeleton variant="line" />
      </div>
    );
  } else if (query.data.total === 0) {
    content = (
      <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
        <CheckCircle aria-hidden className="size-8 text-success-strong" weight="duotone" />
        <p className="max-w-prose text-body text-muted">{t('dashboard.findings.empty')}</p>
      </div>
    );
  } else {
    // Cảnh báo trước, góp ý sau; mỗi mức mới nhất trước.
    const rank = (severity: ImprovementFinding['severity']) => (severity === 'warning' ? 0 : 1);
    const findings = [...query.data.findings]
      .sort((left, right) => rank(left.severity) - rank(right.severity) || Date.parse(right.last_seen) - Date.parse(left.last_seen))
      .slice(0, 5);
    content = (
      <ul className="grid divide-y divide-border">
        {findings.map((finding) => (
          <li key={finding.finding_id} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-3">
            <Tag state={finding.severity === 'warning' ? 'warning' : 'neutral'}>
              {t(`improvement.severity.${finding.severity}`)}
            </Tag>
            <span className="min-w-0 truncate text-body font-medium text-ink">
              {t(`improvement.detector.${finding.detector_id}.title`)}
            </span>
            <span aria-hidden className="text-muted">·</span>
            <Link
              to={`/app/prompts/${encodeURIComponent(finding.prompt_id)}`}
              className="min-w-0 truncate text-caption text-link hover:underline focus-visible:outline-2 focus-visible:outline-focus"
            >
              {titles.get(finding.prompt_id) ?? finding.prompt_id}
            </Link>
            <span className="ml-auto shrink-0 text-caption text-muted">
              {t('improvement.inbox.occurrences', { count: finding.occurrence_count })}
            </span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <Card
      title={t('dashboard.findings.title')}
      description={t('dashboard.findings.description')}
      action={(
        <Link to="/app/improvement" className="text-body text-link hover:underline focus-visible:outline-2 focus-visible:outline-focus">
          {t('dashboard.findings.viewAll')}
        </Link>
      )}
    >
      {content}
    </Card>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  // Bản đồ prompt → tiêu đề cho hai danh sách. Một request duy nhất, chia sẻ
  // promise in-flight với mọi caller khác của GET /prompts.
  const promptsQuery = useQuery(promptsOptions);
  const titles = useMemo(
    () => new Map((promptsQuery.data ?? []).map((prompt) => [prompt.id, prompt.title])),
    [promptsQuery.data],
  );

  return (
    <div className="grid gap-6">
      <PageIntro
        title={t('workspace.sections.home.title')}
        description={t('workspace.sections.home.description')}
      />

      <section aria-label={t('workspace.sections.home.title')} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <TotalPromptsTile />
        <ApprovedTile />
        <PendingReviewsTile />
        <FindingsTile />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <div id="dashboard-review-queue" className="scroll-mt-24">
          <ReviewQueueCard titles={titles} />
        </div>
        <RecentPromptsCard />
      </div>

      <FindingsCard titles={titles} />
    </div>
  );
}

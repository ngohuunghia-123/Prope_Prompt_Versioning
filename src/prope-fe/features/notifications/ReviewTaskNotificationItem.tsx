import { BellSimple, CheckCircle, Fire, ShieldWarning } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import type { ReviewTask } from '@/features/prompt-lifecycle/releaseTypes';
import { cn } from '@/lib/cn';

interface ReviewTaskNotificationItemProps {
  task: ReviewTask;
  last: boolean;
  dateFormatter: Intl.DateTimeFormat;
}

export function ReviewTaskNotificationItem({ task, last, dateFormatter }: ReviewTaskNotificationItemProps) {
  const { t } = useTranslation();
  const Icon = task.status === 'closed'
    ? CheckCircle
    : task.kind === 'break_glass_followup' ? ShieldWarning : BellSimple;
  const occurredAt = task.closed_at ?? task.created_at;
  const title = t(`navigation.advanced.updates.kinds.${task.kind}`);

  return (
    <Link
      to={`/app/prompts/${encodeURIComponent(task.prompt_id)}?tab=release`}
      className={cn(
        'grid grid-cols-[2rem_minmax(0,1fr)] items-start gap-2 rounded-control focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
        !last && 'border-b border-border/60 pb-2.5',
      )}
      aria-label={t('navigation.advanced.updates.openNotification', { notification: title })}
    >
      <span className="grid size-8 place-items-center rounded-full bg-surface/60 text-secondary"><Icon aria-hidden className="size-navigation-icon" /></span>
      <span className="min-w-0">
        <span className="flex items-baseline justify-between gap-3 max-navigation-small:grid max-navigation-small:gap-0.5">
          <strong className="text-caption text-link">{title}</strong>
          <time dateTime={occurredAt} className="shrink-0 text-overline font-bold tracking-navigation-time text-navigation-overline uppercase max-navigation-small:-order-1">{dateFormatter.format(new Date(occurredAt))}</time>
        </span>
        <span className="mt-0.5 block text-navigation-detail leading-normal text-muted">
          {t(`navigation.advanced.updates.status.${task.status}`, {
            versionId: task.version_id,
          })}
        </span>
        {task.overdue ? <span className="mt-1 flex items-center gap-1 text-overline font-bold text-danger"><Fire aria-hidden className="size-3" />{t('navigation.advanced.updates.overdue')}</span> : null}
      </span>
    </Link>
  );
}

import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { ReviewTaskNotificationItem } from '@/features/notifications/ReviewTaskNotificationItem';
import { notificationsOptions } from '@/features/notifications/queries';

export interface NavigationUpdatesPanelProps {
  active: boolean;
}

export function NavigationUpdatesPanel({ active }: NavigationUpdatesPanelProps) {
  const { t, i18n } = useTranslation();
  const notifications = useQuery(notificationsOptions(active));
  const dateFormatter = new Intl.DateTimeFormat(i18n.language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });

  return (
    <section aria-label={t('navigation.advanced.updates.label')} className="h-full animate-navigation-panel overflow-y-auto pb-2.5 pt-1.5 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
      {notifications.isPending ? <p role="status" className="px-3.5 py-7 text-center text-muted">{t('navigation.advanced.updates.loading')}</p> : null}
      {notifications.isError ? (
        <div className="grid gap-2">
          <Notification tone="error" title={t('navigation.advanced.updates.error')}>
            {t('navigation.advanced.updates.errorBody')}
          </Notification>
          <Button className="justify-self-start" type="button" intent="neutral" size="small" onClick={() => void notifications.refetch()}>
            {t('navigation.advanced.updates.retry')}
          </Button>
        </div>
      ) : null}
      {!notifications.isPending && !notifications.isError && notifications.data.length === 0 ? (
        <Notification tone="info" title={t('navigation.advanced.updates.emptyTitle')}>
          {t('navigation.advanced.updates.emptyBody')}
        </Notification>
      ) : null}
      {!notifications.isPending && !notifications.isError && notifications.data.length > 0 ? (
        <div className="grid gap-2.5">
          <p className="m-0 text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t('navigation.advanced.updates.reviewUpdates')}</p>
          {notifications.data.map((task, index) => (
            <ReviewTaskNotificationItem
              key={task.review_task_id}
              task={task}
              last={index === notifications.data.length - 1}
              dateFormatter={dateFormatter}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}

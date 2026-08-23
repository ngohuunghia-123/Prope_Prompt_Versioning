import { queryOptions } from '@tanstack/react-query';

import { getNotifications, getOpenReviewTasks } from '@/features/notifications/api';

export const notificationKeys = {
  all: ['notifications', 'review-tasks'] as const,
  // Same family as `all` but a distinct cache entry: the dashboard reads the
  // open subset, which is a different answer from the newest-50 mix above.
  open: ['notifications', 'review-tasks', 'open'] as const,
};

export function notificationsOptions(enabled: boolean) {
  return queryOptions({
    queryKey: notificationKeys.all,
    queryFn: getNotifications,
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 15_000 : false,
  });
}

/**
 * The workspace's open review tasks, polled on the same clock as the
 * notification bell — one request feeds both the pending-review tile and the
 * queue card, wherever each happens to be mounted.
 */
export function openReviewTasksOptions() {
  return queryOptions({
    queryKey: notificationKeys.open,
    queryFn: getOpenReviewTasks,
    staleTime: 30_000,
    refetchInterval: 15_000,
  });
}

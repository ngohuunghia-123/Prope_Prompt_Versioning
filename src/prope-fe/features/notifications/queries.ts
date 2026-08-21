import { queryOptions } from '@tanstack/react-query';

import { getNotifications } from '@/features/notifications/api';

export const notificationKeys = {
  all: ['notifications', 'review-tasks'] as const,
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

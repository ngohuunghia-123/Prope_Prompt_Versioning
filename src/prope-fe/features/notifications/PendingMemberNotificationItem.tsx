import { UserPlus } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import type { Member } from '@/features/workspace/memberTypes';

interface PendingMemberNotificationItemProps {
  member: Member;
  last: boolean;
  dateFormatter: Intl.DateTimeFormat;
}

export function PendingMemberNotificationItem({ member, last, dateFormatter }: PendingMemberNotificationItemProps) {
  const { t } = useTranslation();
  const name = member.displayName ?? member.email ?? member.userId;

  return (
    <Link
      to="/app/settings/workspace"
      className={`grid grid-cols-[2rem_minmax(0,1fr)] items-start gap-2 rounded-control focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${last ? '' : 'border-b border-border/60 pb-2.5'}`}
      aria-label={t('navigation.advanced.updates.openNotification')}
    >
      <span className="grid size-8 place-items-center rounded-full bg-surface/60 text-secondary"><UserPlus aria-hidden className="size-navigation-icon" /></span>
      <span className="min-w-0">
        <span className="flex items-baseline justify-between gap-3 max-navigation-small:grid max-navigation-small:gap-0.5">
          <strong className="text-caption text-link">{t('navigation.advanced.updates.pendingMember.title')}</strong>
          <time dateTime={member.addedAt} className="shrink-0 text-overline font-bold tracking-navigation-time text-navigation-overline uppercase max-navigation-small:-order-1">{dateFormatter.format(new Date(member.addedAt))}</time>
        </span>
        <span className="mt-0.5 block text-navigation-detail leading-normal text-muted">{t('navigation.advanced.updates.pendingMember.body', { name })}</span>
      </span>
    </Link>
  );
}

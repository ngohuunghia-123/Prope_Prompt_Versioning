import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { sessionOptions } from '@/features/auth/queries';

export function useWorkspaceAccountIdentity() {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);
  const name = session.data?.user.displayName ?? t('navigation.advanced.home.accountName');
  const initials = name.split(/\s+/).filter(Boolean).map((part) => part[0]).slice(-2).join('').toUpperCase();
  return { initials, name, session };
}

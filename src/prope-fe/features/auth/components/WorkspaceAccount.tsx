import { SignOut } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { sessionOptions, useLogoutMutation } from '@/features/auth/queries';

export function WorkspaceAccount() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const session = useQuery(sessionOptions);
  const logout = useLogoutMutation();
  if (!session.data) return null;
  const initials = session.data.user.displayName.split(' ').map((part) => part[0]).slice(-2).join('');
  const handleLogout = async () => {
    await logout.mutateAsync();
    void navigate('/', { replace: true });
  };
  return (
    <div className="flex items-center gap-3 rounded-xl bg-surface p-3 shadow-inset">
      <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-full bg-hero text-caption font-bold text-inverse">{initials}</span>
      <span className="min-w-0 flex-1">
        <strong className="block truncate text-body text-ink">{session.data.user.displayName}</strong>
        <span className="block truncate text-caption text-muted">{t(`roles.${session.data.user.role}`)}</span>
      </span>
      <Button type="button" size="icon" intent="neutral" loading={logout.isPending} onClick={() => void handleLogout()} aria-label={t('auth.logout')}>
        <SignOut aria-hidden className="size-4" />
      </Button>
    </div>
  );
}

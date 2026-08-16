import { SignOut } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { useLogoutMutation } from '@/features/auth/queries';
import { useWorkspaceAccountIdentity } from '@/features/auth/components/useWorkspaceAccountIdentity';

export function WorkspaceAccount() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { initials, name, session } = useWorkspaceAccountIdentity();
  const logout = useLogoutMutation();
  if (!session.data) {
    return <a href="/app/account" className="mt-1 flex min-h-13 min-w-0 items-center gap-2.5 rounded-navigation-panel bg-canvas p-2.5 text-ink shadow-inset transition-colors hover:bg-surface hover:text-link focus-visible:outline-2 focus-visible:outline-focus"><span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-full bg-navigation-avatar text-overline font-bold">LP</span><span className="min-w-0"><strong className="block truncate text-navigation-strong font-semibold">{t('navigation.advanced.home.accountName')}</strong><span className="block truncate text-overline text-muted">{t('navigation.advanced.home.accountPlan')}</span></span></a>;
  }
  const handleLogout = async () => {
    try {
      await logout.mutateAsync();
      void navigate('/login', { replace: true });
    } catch {
      // The mutation error keeps the account visible and offers a retry.
    }
  };
  return (
    <div className="rounded-xl bg-surface p-3 shadow-inset">
      <div className="flex items-center gap-3">
        {/* The identity is the link and the sign-out stays its own button. The
            collapsed rail's avatar has always pointed at /app/account; this is
            the same destination from the expanded card. */}
        <Link
          to="/app/account"
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg transition-colors hover:text-link focus-visible:outline-2 focus-visible:outline-focus"
        >
          <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-full bg-hero text-caption font-bold text-inverse">{initials}</span>
          <span className="min-w-0 flex-1">
            <strong className="block truncate text-body text-ink">{name}</strong>
            <span className="block truncate text-caption text-muted">{t(`roles.${session.data.user.role}`)} · {session.data.user.workspaceName}</span>
          </span>
        </Link>
        <Button type="button" size="icon" intent="neutral" loading={logout.isPending} onClick={() => void handleLogout()} aria-label={t('auth.logout')}>
          <SignOut aria-hidden className="size-4" />
        </Button>
      </div>
      {logout.isError ? <p role="alert" className="mt-2 text-caption text-danger-text">{t('auth.logoutError')}</p> : null}
    </div>
  );
}

import { Key, SignOut, UserCircle, Warning } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { sessionOptions, useLogoutMutation } from '@/features/auth/queries';

/**
 * Who you are signed in as, from the session row itself.
 *
 * Everything here comes from `GET /api/v1/session` — display name, email, the
 * role that decided what the rest of the app let you do, and when the row
 * expires. Nothing on this page is editable, because nothing behind it is: there
 * is no profile endpoint, and the one thing a person *can* change about
 * themselves is their password, which has its own screen.
 *
 * `/app/account` had a link in the navigation footer and no route, so it fell
 * through `PromptLifecycleRoutes`' catch-all onto the prompt registry.
 */
export function AccountPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const session = useQuery(sessionOptions);
  const logout = useLogoutMutation();

  if (session.isPending) return <QueryState state="loading" />;
  if (session.isError) return <QueryState state="error" onRetry={() => void session.refetch()} />;
  if (!session.data) return <QueryState state="empty" />;

  const { user, expiresAt, mustChangePassword } = session.data;
  const initials = user.displayName.split(/\s+/).filter(Boolean).map((part) => part[0]).slice(-2).join('').toUpperCase();

  const signOut = async () => {
    try {
      await logout.mutateAsync();
      void navigate('/login', { replace: true });
    } catch {
      // The error below keeps the page visible and offers another attempt.
    }
  };

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-6">
      <PageIntro
        eyebrow={t('account.eyebrow')}
        title={t('account.title')}
        description={t('account.description')}
      />

      {/* The server sets this on a provisioned password. Said here as well as at
          login, because this is the screen somebody lands on to deal with it. */}
      {mustChangePassword ? (
        <Notification tone="info" title={t('account.mustChangePasswordTitle')}>
          {t('account.mustChangePassword')}
        </Notification>
      ) : null}

      <Card title={t('account.identity')}>
        <div className="mt-2 flex flex-wrap items-center gap-4">
          <span aria-hidden className="grid size-14 shrink-0 place-items-center rounded-full bg-hero text-heading-3 font-bold text-inverse">
            {initials}
          </span>
          <div className="min-w-0">
            <strong className="block truncate text-heading-3 text-ink">{user.displayName}</strong>
            <span className="block truncate text-body text-muted">{user.email}</span>
          </div>
        </div>

        <dl className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-border bg-subtle p-4">
            <dt className="text-caption text-muted">{t('account.role')}</dt>
            <dd className="mt-2 text-body font-medium text-ink">{t(`roles.${user.role}`)}</dd>
          </div>
          <div className="rounded-xl border border-border bg-subtle p-4">
            <dt className="text-caption text-muted">{t('account.workspace')}</dt>
            <dd className="mt-2 truncate text-body font-medium text-ink">{user.workspaceName}</dd>
          </div>
          <div className="rounded-xl border border-border bg-subtle p-4">
            {/* A server-side session row with an expiry, not a token — so this
                date is when you will actually be asked to sign in again. */}
            <dt className="text-caption text-muted">{t('account.sessionExpires')}</dt>
            <dd className="mt-2 text-body font-medium text-ink">{format.date(expiresAt)}</dd>
          </div>
        </dl>
      </Card>

      <Card title={t('account.security')}>
        <p className="mt-2 text-body text-muted">{t('account.securityBody')}</p>
        <div className="mt-4 flex flex-wrap gap-2.5">
          <Button
            type="button"
            intent="neutral"
            leadingIcon={<Key aria-hidden className="size-4" />}
            onClick={() => void navigate('/change-password')}
          >
            {t('account.changePassword')}
          </Button>
          <Button
            type="button"
            intent="neutral"
            loading={logout.isPending}
            leadingIcon={<SignOut aria-hidden className="size-4" />}
            onClick={() => void signOut()}
          >
            {t('auth.logout')}
          </Button>
        </div>
        {logout.isError ? (
          <p role="alert" className="mt-3 flex items-center gap-2 text-caption text-danger-text">
            <Warning aria-hidden className="size-4" />
            {t('auth.logoutError')}
          </p>
        ) : null}
      </Card>

      <p className="flex items-center gap-2 text-caption text-muted">
        <UserCircle aria-hidden className="size-4" />
        {t('account.readOnlyNote')}
      </p>
    </div>
  );
}

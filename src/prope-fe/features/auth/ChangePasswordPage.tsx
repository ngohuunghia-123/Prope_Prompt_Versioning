import { Key } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { Button } from '@/components/ui/Button';
import { RouteLoadingState } from '@/components/ui/RouteLoadingState';
import { ChangePasswordForm } from '@/features/auth/components/ChangePasswordForm';
import { sessionOptions } from '@/features/auth/queries';
import { getLoginPath, getReturnTo } from '@/features/auth/returnTo';

export function ChangePasswordPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const session = useQuery(sessionOptions);
  const returnTo = getReturnTo(location.search);

  if (session.isPending) return <RouteLoadingState label={t('common.loading')} kind="form" />;
  if (session.isError) {
    return (
      <main className="grid min-h-dvh place-items-center bg-canvas p-4">
        <div className="max-w-auth rounded-visual border border-border bg-surface p-6 text-center shadow-floating">
          <p role="alert" className="text-body text-danger-text">{t('auth.sessionCheckError')}</p>
          <Button className="mt-4" type="button" intent="neutral" onClick={() => void session.refetch()}>{t('common.tryAgain')}</Button>
        </div>
      </main>
    );
  }
  if (!session.data) return <Navigate to={getLoginPath(returnTo)} replace />;
  if (!session.data.mustChangePassword) return <Navigate to={returnTo} replace />;

  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-4 py-12 sm:px-8">
      <section className="w-full max-w-auth" aria-labelledby="change-password-title">
        <Logo />
        <div className="mt-8 rounded-visual border border-border bg-surface p-6 shadow-floating sm:p-8">
          <span aria-hidden className="grid size-11 place-items-center rounded-full bg-subtle text-secondary"><Key className="size-5" /></span>
          <p className="mt-6 text-overline font-semibold uppercase tracking-button text-secondary">{t('auth.changePassword.eyebrow')}</p>
          <h1 id="change-password-title" className="mt-3 font-display text-display-2 font-semibold text-ink">{t('auth.changePassword.title')}</h1>
          <p className="mt-3 text-body text-muted">{t('auth.changePassword.description')}</p>
          <div className="mt-8"><ChangePasswordForm /></div>
        </div>
      </section>
    </main>
  );
}

import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { Button } from '@/components/ui/Button';
import { RouteLoadingState } from '@/components/ui/RouteLoadingState';
import { AuthModeSwitch } from '@/features/auth/components/AuthModeSwitch';
import { AuthVisualCarousel } from '@/features/auth/components/AuthVisualCarousel';
import { LoginForm } from '@/features/auth/components/LoginForm';
import { SignupForm } from '@/features/auth/components/SignupForm';
import { sessionOptions } from '@/features/auth/queries';
import { getChangePasswordPath, getReturnTo } from '@/features/auth/returnTo';

export function LoginPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const mode = location.pathname === '/signup' ? 'signup' : 'login';
  const session = useQuery(sessionOptions);
  const returnTo = getReturnTo(location.search);
  const sessionExpired = typeof location.state === 'object' && location.state !== null && 'sessionExpired' in location.state && location.state.sessionExpired === true;
  if (session.isPending) return <RouteLoadingState label={t('common.loading')} kind="auth" />;
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
  if (session.data) return <Navigate to={session.data.mustChangePassword ? getChangePasswordPath(returnTo) : returnTo} replace />;
  return (
    <main className="grid min-h-dvh bg-canvas lg:grid-cols-2">
      <AuthVisualCarousel />
      <section className="relative isolate flex items-start justify-center overflow-x-hidden overflow-y-auto px-4 py-6 sm:px-8 sm:py-8 lg:col-start-2 lg:h-dvh lg:items-center">
        <img src="/auth-mobile/sky-mountains.webp" alt="" aria-hidden className="absolute inset-0 -z-10 size-full object-cover opacity-auth-mobile-background lg:hidden" />
        <div className="relative z-10 flex w-full max-w-auth flex-col items-center text-center">
          <Link to="/" className="inline-flex w-fit rounded-control focus-visible:outline-2 focus-visible:outline-focus" aria-label={t('common.propeHome')}><Logo /></Link>
          <h1 className="mt-8 font-display text-auth-heading-mobile font-semibold text-ink sm:text-heading-1">{t('auth.valuePrompt')}</h1>
          <div className="mt-8 w-full">
            <AuthModeSwitch value={mode} />
          </div>
          <div className="mt-8 w-full text-left">
            {sessionExpired ? <p role="status" className="mb-5 rounded-lg bg-warning p-3 text-body text-ink">{t('auth.sessionExpired')}</p> : null}
            {mode === 'signup' ? <SignupForm /> : <LoginForm />}
          </div>
        </div>
      </section>
    </main>
  );
}

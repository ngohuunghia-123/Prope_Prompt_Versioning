import { CheckCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { Button } from '@/components/ui/Button';
import { LoginForm } from '@/features/auth/components/LoginForm';
import { sessionOptions } from '@/features/auth/queries';
import { getChangePasswordPath, getReturnTo } from '@/features/auth/returnTo';

export function LoginPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const session = useQuery(sessionOptions);
  const returnTo = getReturnTo(location.search);
  const sessionExpired = typeof location.state === 'object' && location.state !== null && 'sessionExpired' in location.state && location.state.sessionExpired === true;
  if (session.isPending) return <div className="grid min-h-dvh place-items-center bg-canvas text-body text-muted">{t('common.loading')}</div>;
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
      <section className="relative hidden overflow-hidden bg-hero p-12 text-inverse lg:flex lg:flex-col lg:justify-end">
        <img src="/assets/landing/footer-green-mountain-v3.webp" alt="" className="absolute inset-0 size-full object-cover opacity-45" />
        <div className="absolute inset-0 bg-gradient-to-b from-hero/35 to-hero" />
        <div className="relative z-10 max-w-copy">
          <p className="text-overline font-semibold uppercase tracking-button text-primary">{t('auth.visualEyebrow')}</p>
          <h1 className="mt-4 font-display text-auth-visual font-semibold">{t('auth.visualTitle')}</h1>
          <ul className="mt-8 space-y-3 text-body-large text-landing-muted">
            {(['ownership', 'evidence', 'release'] as const).map((item) => <li key={item} className="flex items-center gap-3"><CheckCircle aria-hidden className="size-5 text-primary" />{t(`auth.benefits.${item}`)}</li>)}
          </ul>
        </div>
      </section>
      <section className="flex items-center justify-center px-4 py-16 sm:px-8">
        <div className="w-full max-w-auth">
          <Link to="/" className="inline-flex w-fit rounded-control focus-visible:outline-2 focus-visible:outline-focus" aria-label={t('common.propeHome')}><Logo /></Link>
          <h1 className="mt-8 font-display text-heading-1 font-semibold text-ink">{t('auth.valuePrompt')}</h1>
          <div className="mt-10">
            {sessionExpired ? <p role="status" className="mb-5 rounded-lg bg-warning p-3 text-body text-ink">{t('auth.sessionExpired')}</p> : null}
            <LoginForm />
          </div>
        </div>
      </section>
    </main>
  );
}

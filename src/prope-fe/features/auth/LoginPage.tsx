import { ArrowLeft, CheckCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, Navigate } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { LoginForm } from '@/features/auth/components/LoginForm';
import { sessionOptions } from '@/features/auth/queries';

export function LoginPage() {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);
  if (session.data) return <Navigate to="/app/prompts" replace />;
  return (
    <main className="grid min-h-dvh bg-canvas lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-hero p-12 text-inverse lg:flex lg:flex-col lg:justify-between">
        <img src="/assets/landing/footer-green-mountain-v3.webp" alt="" className="absolute inset-0 size-full object-cover opacity-45" />
        <div className="absolute inset-0 bg-gradient-to-b from-hero/35 to-hero" />
        <Link to="/" className="relative z-10 w-fit" aria-label={t('common.propeHome')}><Logo inverse /></Link>
        <div className="relative z-10 max-w-copy">
          <p className="text-overline font-semibold uppercase tracking-button text-primary">{t('auth.visualEyebrow')}</p>
          <h1 className="mt-4 font-display text-section font-semibold">{t('auth.visualTitle')}</h1>
          <ul className="mt-8 space-y-3 text-body-large text-landing-muted">
            {(['ownership', 'evidence', 'release'] as const).map((item) => <li key={item} className="flex items-center gap-3"><CheckCircle aria-hidden className="size-5 text-primary" />{t(`auth.benefits.${item}`)}</li>)}
          </ul>
        </div>
      </section>
      <section className="flex items-center justify-center px-4 py-16 sm:px-8">
        <div className="w-full max-w-auth">
          <div className="mb-10 flex items-center justify-between lg:hidden"><Logo /><Link to="/" aria-label={t('auth.back')} className="grid size-10 place-items-center rounded-full text-muted hover:bg-subtle"><ArrowLeft aria-hidden className="size-5" /></Link></div>
          <p className="text-overline font-semibold uppercase tracking-button text-secondary">{t('auth.eyebrow')}</p>
          <h1 className="mt-3 font-display text-display-2 font-semibold text-ink sm:text-display-1">{t('auth.title')}</h1>
          <p className="mt-4 text-body-large text-muted">{t('auth.description')}</p>
          <div className="mt-8 rounded-visual border border-border bg-surface p-6 shadow-floating sm:p-8">
            <LoginForm />
            <div className="mt-6 rounded-lg bg-subtle p-4 text-caption text-muted"><strong className="block text-ink">{t('auth.demoTitle')}</strong><span className="mt-1 block">{t('auth.demoCredentials')}</span></div>
          </div>
          <p className="mt-6 text-center text-caption text-muted">{t('auth.noSignup')}</p>
        </div>
      </section>
    </main>
  );
}

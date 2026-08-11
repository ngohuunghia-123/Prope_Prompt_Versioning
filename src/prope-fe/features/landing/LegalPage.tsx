import { ArrowLeft } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { Logo } from '@/components/Logo';

export function LegalPage() {
  const { t } = useTranslation();
  const isPrivacy = useLocation().pathname === '/privacy';
  const type = isPrivacy ? 'privacy' : 'terms';
  return <main className="min-h-dvh bg-canvas px-4 py-10 sm:px-6"><div className="mx-auto max-w-copy"><Link to="/"><Logo /></Link><Link to="/" className="mt-14 flex w-fit items-center gap-2 text-body font-semibold text-link"><ArrowLeft aria-hidden className="size-4" />{t('legal.back')}</Link><h1 className="mt-8 font-display text-display-2 font-semibold">{t(`legal.${type}.title`)}</h1><p className="mt-5 text-body-large leading-relaxed text-muted">{t(`legal.${type}.body`)}</p><p className="mt-8 rounded-xl bg-subtle p-5 text-body text-muted">{t('legal.placeholder')}</p></div></main>;
}

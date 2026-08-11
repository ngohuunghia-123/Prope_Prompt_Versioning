import { ArrowRight, BookOpenText, ClockCounterClockwise, ShieldCheck } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { buttonVariants } from '@/components/ui/buttonVariants';
import { cn } from '@/lib/cn';

export function OnboardingPage() {
  const { t } = useTranslation();
  const benefits = [
    { key: 'preserve', icon: <ShieldCheck aria-hidden className="size-6" /> },
    { key: 'find', icon: <BookOpenText aria-hidden className="size-6" /> },
    { key: 'reuse', icon: <ClockCounterClockwise aria-hidden className="size-6" /> },
  ] as const;
  return (
    <main className="min-h-dvh bg-canvas p-4 text-ink sm:p-6 lg:p-8">
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-content flex-col overflow-hidden rounded-panel border border-border bg-surface shadow-floating lg:grid lg:grid-cols-[minmax(0,1.15fr)_minmax(22rem,0.85fr)]">
        <section className="relative flex flex-col justify-between overflow-hidden bg-hero p-7 text-inverse sm:p-10 lg:p-14">
          <div aria-hidden className="absolute -right-24 -top-24 size-80 rounded-full bg-hero-soft/20 blur-3xl" />
          <Logo inverse className="relative" />
          <div className="relative my-16 max-w-copy lg:my-0">
            <p className="text-overline font-semibold tracking-button text-landing-muted">{t('preservation.onboarding.eyebrow')}</p>
            <h1 className="mt-4 font-display text-display-2 font-semibold sm:text-display-1">{t('preservation.onboarding.title')}</h1>
            <p className="mt-5 max-w-auth text-body-large leading-7 text-landing-muted">{t('preservation.onboarding.description')}</p>
          </div>
          <p className="relative text-caption text-landing-muted">{t('preservation.onboarding.privacy')}</p>
        </section>
        <section className="flex flex-col justify-center p-7 sm:p-10 lg:p-14" aria-labelledby="onboarding-benefits">
          <p className="text-overline font-semibold text-muted">{t('preservation.onboarding.step')}</p>
          <h2 id="onboarding-benefits" className="mt-2 text-heading-1 font-semibold">{t('preservation.onboarding.benefitsTitle')}</h2>
          <ul className="mt-8 space-y-5">
            {benefits.map((benefit) => <li key={benefit.key} className="flex gap-4"><span className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-soft text-link">{benefit.icon}</span><div><h3 className="font-sans text-body-large font-semibold">{t(`preservation.onboarding.benefits.${benefit.key}.title`)}</h3><p className="mt-1 text-body text-muted">{t(`preservation.onboarding.benefits.${benefit.key}.body`)}</p></div></li>)}
          </ul>
          <div className="mt-10 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <Link to="/app/prompts/new" className={cn(buttonVariants({ intent: 'primary' }), 'sm:shrink-0 sm:whitespace-nowrap')}>{t('preservation.onboarding.firstPrompt')}<ArrowRight aria-hidden className="size-4" /></Link>
            <Link to="/app/prompts" className={cn(buttonVariants({ intent: 'neutral' }), 'sm:shrink-0 sm:whitespace-nowrap')}>{t('preservation.onboarding.returning')}</Link>
          </div>
        </section>
      </div>
    </main>
  );
}

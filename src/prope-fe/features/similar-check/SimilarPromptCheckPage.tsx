import { ArrowLeft, Flask, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { similarAvailabilityOptions, useCheckSimilar } from '@/features/similar-check/api';
import { SimilarCheckForm } from '@/features/similar-check/components/SimilarCheckForm';
import { SimilarResults } from '@/features/similar-check/components/SimilarResults';
import type { SimilarCheckFormValues } from '@/features/similar-check/types';

export function SimilarPromptCheckPage() {
  const { t } = useTranslation();
  const availability = useQuery(similarAvailabilityOptions);
  const check = useCheckSimilar();
  const submit = (values: SimilarCheckFormValues) => check.mutate(values);
  return <PreservationShell activeId="prompts" title={t('similar.pageTitle')} description={t('similar.pageDescription')} showCreate={false}>
    <div className="mx-auto max-w-copy space-y-5"><Link to="/app/prompts/new" className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('similar.actions.back')}</Link>
      <header className="rounded-panel border border-info-strong bg-info p-5 shadow-floating sm:p-8"><Flask aria-hidden className="size-9 text-info-strong" weight="fill" /><p className="mt-5 text-overline font-semibold text-info-strong">{t('similar.hero.eyebrow')}</p><h1 className="mt-2 text-heading-1 font-semibold sm:text-display-2">{t('similar.hero.title')}</h1><p className="mt-3 text-body-large text-muted">{t('similar.hero.description')}</p></header>
      {availability.isPending ? <div className="h-72 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
      {availability.isError ? <section role="alert" className="grid min-h-72 place-items-center rounded-panel border border-danger-strong bg-danger p-6 text-center"><div><WarningCircle aria-hidden className="mx-auto size-10 text-danger-text" /><h2 className="mt-4 text-heading-2 font-semibold">{t('similar.states.error.title')}</h2><p className="mt-2 text-body text-danger-text">{t('similar.states.error.body')}</p></div></section> : null}
      {availability.data && !availability.data.available ? <Notification className="max-w-none" tone="info" title={t('similar.states.empty.title')}>{t('similar.states.empty.body')}</Notification> : null}
      {availability.data?.available ? <><SimilarCheckForm checking={check.isPending} onSubmit={submit} />{check.isError ? <Notification className="max-w-none" tone="error" title={t('similar.notices.errorTitle')}>{t('similar.notices.errorBody')}</Notification> : null}{check.data ? <SimilarResults result={check.data} /> : null}</> : null}
    </div>
  </PreservationShell>;
}

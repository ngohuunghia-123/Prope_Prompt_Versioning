import { ArrowClockwise } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { PromptPortfolio } from '@/features/preservation/components/PromptPortfolio';
import { promptListOptions } from '@/features/preservation/queries';

export function PromptPortfolioPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const prompts = useQuery(promptListOptions);
  const focusSearch = searchParams.get('focus') === 'search';
  return (
    <PreservationShell activeId="registry" title={t('preservation.portfolio.title')} description={t('preservation.portfolio.description')}>
      {prompts.isPending ? <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3" aria-label={t('common.loading')}>{[0, 1, 2].map((item) => <div key={item} className="h-64 animate-pulse rounded-modal bg-subtle motion-reduce:animate-none" />)}</div> : null}
      {prompts.isError ? <section role="alert" className="grid min-h-80 place-items-center rounded-modal border border-danger-strong bg-danger p-6 text-center"><div><h2 className="text-heading-2 font-semibold">{t('preservation.error.title')}</h2><p className="mt-2 text-body text-danger-text">{t('preservation.error.body')}</p><Button intent="neutral" className="mt-5" leadingIcon={<ArrowClockwise aria-hidden className="size-4" />} onClick={() => void prompts.refetch()}>{t('preservation.actions.retry')}</Button></div></section> : null}
      {prompts.data ? <PromptPortfolio prompts={prompts.data} initialFocus={focusSearch} /> : null}
    </PreservationShell>
  );
}

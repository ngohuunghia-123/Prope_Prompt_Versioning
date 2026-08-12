import { BookOpenText, MagnifyingGlass, Plus } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { buttonVariants } from '@/components/ui/buttonVariants';

export interface PortfolioEmptyStateProps { filtered: boolean; onClear?: () => void; }

export function PortfolioEmptyState({ filtered, onClear }: PortfolioEmptyStateProps) {
  const { t } = useTranslation();
  const Icon = filtered ? MagnifyingGlass : BookOpenText;
  return (
    <section className="col-span-full grid min-h-96 place-items-center overflow-hidden rounded-panel border border-border bg-surface p-6 text-center shadow-panel">
      <div className="max-w-copy">
        <span aria-hidden className="mx-auto grid size-20 place-items-center rounded-full bg-accent-soft text-link"><Icon className="size-9" /></span>
        <h2 className="mt-6 text-heading-2 font-semibold">{t(filtered ? 'preservation.empty.noResultsTitle' : 'preservation.empty.title')}</h2>
        <p className="mx-auto mt-3 max-w-auth text-body-large text-muted">{t(filtered ? 'preservation.empty.noResultsBody' : 'preservation.empty.body')}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {filtered && onClear ? <button type="button" onClick={onClear} className={buttonVariants({ intent: 'neutral' })}>{t('preservation.actions.clearFilters')}</button> : null}
          <Link to="/app/prompts/new" className={buttonVariants({ intent: 'primary' })}><Plus aria-hidden className="size-4" />{t('preservation.actions.add')}</Link>
        </div>
      </div>
    </section>
  );
}

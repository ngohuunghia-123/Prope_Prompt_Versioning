import { BookOpenText, MagnifyingGlass, Plus } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { buttonVariants } from '@/components/ui/buttonVariants';

export interface RegistryEmptyStateProps { filtered: boolean; onClear: () => void; }

export function RegistryEmptyState({ filtered, onClear }: RegistryEmptyStateProps) {
  const { t } = useTranslation();
  const Icon = filtered ? MagnifyingGlass : BookOpenText;
  return (
    <section className="col-span-full grid min-h-80 place-items-center rounded-panel border border-border bg-surface p-6 text-center shadow-panel">
      <div className="max-w-copy">
        <span aria-hidden className="mx-auto grid size-16 place-items-center rounded-full bg-accent-soft text-link"><Icon className="size-7" /></span>
        <h2 className="mt-5 text-heading-2 font-semibold">{t(filtered ? 'trustedRegistry.empty.noResultsTitle' : 'trustedRegistry.empty.registryTitle')}</h2>
        <p className="mx-auto mt-2 max-w-auth text-body text-muted">{t(filtered ? 'trustedRegistry.empty.noResultsBody' : 'trustedRegistry.empty.registryBody')}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {filtered ? <Button intent="neutral" onClick={onClear}>{t('trustedRegistry.actions.clear')}</Button> : null}
          <Link to="/app/prompts/new" className={buttonVariants({ intent: 'primary' })}><Plus aria-hidden className="size-4" />{t('trustedRegistry.actions.add')}</Link>
        </div>
      </div>
    </section>
  );
}


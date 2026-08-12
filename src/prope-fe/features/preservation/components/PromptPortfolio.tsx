import { FunnelSimple, MagnifyingGlass } from '@phosphor-icons/react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { PortfolioEmptyState } from '@/features/preservation/components/PortfolioEmptyState';
import { PromptCard } from '@/features/preservation/components/PromptCard';
import type { PreservedPrompt } from '@/features/preservation/types';

export interface PromptPortfolioProps { prompts: PreservedPrompt[]; initialFocus?: boolean; }

export function PromptPortfolio({ prompts, initialFocus = false }: PromptPortfolioProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const visiblePrompts = useMemo(() => {
    const normalized = search.trim().toLocaleLowerCase();
    return prompts.filter((prompt) => {
      const matchesStatus = status === 'all' || prompt.status === status;
      const searchable = [prompt.title, prompt.purpose, ...prompt.tags].join(' ').toLocaleLowerCase();
      return matchesStatus && (!normalized || searchable.includes(normalized));
    });
  }, [prompts, search, status]);
  const filtered = Boolean(search.trim()) || status !== 'all';
  const clear = () => { setSearch(''); setStatus('all'); };

  return (
    <div className="space-y-6">
      <section aria-label={t('preservation.portfolio.filters')} className="grid gap-4 rounded-modal border border-border bg-surface p-4 shadow-floating sm:grid-cols-[minmax(0,1fr)_14rem] sm:p-5">
        <div className="relative"><MagnifyingGlass aria-hidden className="pointer-events-none absolute right-3 top-9 size-5 text-muted" /><Input autoFocus={initialFocus} label={t('preservation.portfolio.search')} placeholder={t('preservation.portfolio.searchPlaceholder')} value={search} onChange={(event) => setSearch(event.target.value)} className="pr-10" /></div>
        <div className="relative"><FunnelSimple aria-hidden className="pointer-events-none absolute right-9 top-9 z-10 size-4 text-muted" /><Select label={t('preservation.portfolio.status')} value={status} onValueChange={setStatus} options={[{ value: 'all', label: t('preservation.portfolio.all') }, { value: 'ready', label: t('preservation.status.ready') }, { value: 'draft', label: t('preservation.status.draft') }]} /></div>
      </section>
      <div className="flex items-end justify-between gap-4"><div><p className="text-overline font-semibold text-muted">{t('preservation.portfolio.collection')}</p><h2 className="mt-1 text-heading-2 font-semibold">{t('preservation.portfolio.resultCount', { count: visiblePrompts.length })}</h2></div></div>
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {visiblePrompts.length ? visiblePrompts.map((prompt) => <PromptCard key={prompt.id} prompt={prompt} />) : <PortfolioEmptyState filtered={filtered} onClear={clear} />}
      </div>
    </div>
  );
}

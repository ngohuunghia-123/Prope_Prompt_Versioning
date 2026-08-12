import { ArrowRight, MagnifyingGlass, Sparkle, X } from '@phosphor-icons/react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { navigationSearchResults } from '@/components/navigationData';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

export interface NavigationSearchPanelProps { onAskPropAI: (query: string) => void; }

export function NavigationSearchPanel({ onAskPropAI }: NavigationSearchPanelProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLowerCase();
  const results = useMemo(() => navigationSearchResults.filter((item) => !normalizedQuery || item.searchTerms.includes(normalizedQuery)), [normalizedQuery]);
  return (
    <section aria-label={t('navigation.advanced.search.label')} className="h-full animate-navigation-panel overflow-y-auto pb-2.5 pt-1.5 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
      <div className="relative">
        <MagnifyingGlass aria-hidden className="pointer-events-none absolute left-3 top-1/2 z-10 size-navigation-icon -translate-y-1/2 text-secondary" />
        <Input type="search" data-navigation-search-input autoComplete="off" label={t('navigation.advanced.search.inputLabel')} labelHidden value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('navigation.advanced.search.placeholder')} className="px-9 text-caption" />
        {normalizedQuery ? <Button type="button" intent="ghost" size="navigationIcon" onClick={() => setQuery('')} aria-label={t('navigation.advanced.search.clear')} className="absolute right-1 top-1/2 -translate-y-1/2 rounded-full text-muted"><X aria-hidden /></Button> : null}
      </div>
      <Button type="button" intent="ghost" onClick={() => onAskPropAI(query.trim())} className="mt-2.5 grid min-h-12 w-full grid-cols-[2rem_minmax(0,1fr)_1.125rem] items-center gap-2 rounded-navigation-panel bg-surface/80 p-2 text-left normal-case tracking-normal text-ink shadow-inset hover:-translate-y-px hover:bg-surface hover:shadow-raised">
        <span className="grid size-8 place-items-center rounded-navigation-control bg-subtle text-secondary"><Sparkle aria-hidden className="size-navigation-icon" /></span><span className="min-w-0"><strong className="block truncate text-caption">{t('navigation.advanced.search.askPropAI')}</strong><span className="block truncate text-overline font-normal text-muted">{normalizedQuery ? t('navigation.advanced.search.askAboutQuery', { query: query.trim() }) : t('navigation.advanced.search.askAboutProperty')}</span></span><ArrowRight aria-hidden className="size-navigation-icon" />
      </Button>
      <p className="mb-2 mt-4 text-navigation-detail text-muted">{t('navigation.advanced.search.summary', { count: results.length })}</p>
      <div className="grid gap-2">
        {results.map(({ id, icon: Icon, titleKey, descriptionKey, kindKey, href }) => <a key={id} href={href} className="grid min-w-0 grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-2 rounded-navigation-panel bg-surface px-2.5 py-2 text-ink shadow-inset transition-[transform,box-shadow] hover:-translate-y-px hover:shadow-raised focus-visible:outline-2 focus-visible:outline-focus"><span className="grid size-8 place-items-center rounded-navigation-control bg-subtle text-secondary"><Icon aria-hidden className="size-navigation-icon" /></span><span className="min-w-0"><strong className="block truncate text-navigation-strong">{t(`navigation.advanced.search.results.${titleKey}`)}</strong><span className="mt-0.5 block truncate text-overline text-muted">{t(`navigation.advanced.search.results.${descriptionKey}`)}</span></span><span className="text-navigation-kind font-bold tracking-navigation-kind text-navigation-overline uppercase">{t(`navigation.advanced.search.kinds.${kindKey}`)}</span></a>)}
      </div>
      {results.length === 0 ? <div className="px-3.5 py-7 text-center text-muted"><MagnifyingGlass aria-hidden className="mx-auto size-5" /><p>{t('navigation.advanced.search.noResults')}</p></div> : null}
    </section>
  );
}

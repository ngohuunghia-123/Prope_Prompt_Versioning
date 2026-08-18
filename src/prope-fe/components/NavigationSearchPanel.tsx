import { ArrowRight, MagnifyingGlass, Sparkle, X } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { promptSearchOptions } from '@/features/prompt-lifecycle/queries';

export interface NavigationSearchPanelProps {
  onAskPropAI: (query: string) => void;
}

export function NavigationSearchPanel({ onAskPropAI }: NavigationSearchPanelProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'quick' | 'ai'>('quick');
  const search = useQuery({ ...promptSearchOptions(query, mode), enabled: query.length > 0 });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setQuery(draft.trim());
  };

  return (
    <section aria-label={t('navigation.advanced.search.label')} className="h-full animate-navigation-panel overflow-y-auto pb-2.5 pt-1.5 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
      <form onSubmit={submit} className="grid gap-2">
        <div className="relative">
          <MagnifyingGlass aria-hidden className="pointer-events-none absolute left-3 top-1/2 z-10 size-navigation-icon -translate-y-1/2 text-secondary" />
          <Input type="search" data-navigation-search-input autoComplete="off" label={t('navigation.advanced.search.inputLabel')} labelHidden value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={t('promptSearch.placeholder')} className="px-9 text-caption" />
          {draft ? <Button type="button" intent="ghost" size="navigationIcon" onClick={() => { setDraft(''); setQuery(''); }} aria-label={t('navigation.advanced.search.clear')} className="absolute right-1 top-1/2 -translate-y-1/2 rounded-full text-muted"><X aria-hidden /></Button> : null}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button type="button" intent={mode === 'ai' ? 'secondary' : 'neutral'} size="small" leadingIcon={<Sparkle aria-hidden className="size-4" />} onClick={() => setMode((current) => current === 'ai' ? 'quick' : 'ai')}>
            {mode === 'ai' ? t('promptSearch.useQuick') : t('promptSearch.searchWithAi')}
          </Button>
          <Button type="submit" size="small" loading={search.isFetching} disabled={!draft.trim()}>{t('promptSearch.submit')}</Button>
        </div>
      </form>

      <Button type="button" intent="ghost" onClick={() => onAskPropAI(draft.trim())} className="mt-2.5 grid min-h-12 w-full grid-cols-[2rem_minmax(0,1fr)_1.125rem] items-center gap-2 rounded-navigation-panel bg-surface/80 p-2 text-left normal-case tracking-normal text-ink shadow-inset hover:-translate-y-px hover:bg-surface hover:shadow-raised">
        <span className="grid size-8 place-items-center rounded-navigation-control bg-subtle text-secondary"><Sparkle aria-hidden className="size-navigation-icon" /></span>
        <span className="min-w-0"><strong className="block truncate text-caption">{t('navigation.advanced.search.askPropAI')}</strong><span className="block truncate text-overline font-normal text-muted">{draft.trim() ? t('navigation.advanced.search.askAboutQuery', { query: draft.trim() }) : t('navigation.advanced.search.askAboutProperty')}</span></span>
        <ArrowRight aria-hidden className="size-navigation-icon" />
      </Button>

      {query ? <p className="mb-2 mt-4 text-navigation-detail text-muted">{t('navigation.advanced.search.summary', { count: search.data?.prompts.length ?? 0 })}</p> : null}
      {search.isError ? <p role="alert" className="rounded-navigation-panel bg-danger p-3 text-caption text-danger-text">{t('lifecycle.states.error.description')}</p> : null}
      {query && !search.isPending && !search.isError && search.data?.prompts.length === 0 ? <p className="px-3.5 py-7 text-center text-muted">{t('navigation.advanced.search.noResults')}</p> : null}
      <div className="grid gap-2">
        {search.data?.prompts.map((result) => (
          <button key={result.prompt_id} type="button" onClick={() => void navigate(`/app/prompts/${encodeURIComponent(result.prompt_id)}`)} className="grid min-w-0 cursor-pointer grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-2 rounded-navigation-panel bg-surface px-2.5 py-2 text-left text-ink shadow-inset transition-[transform,box-shadow] hover:-translate-y-px hover:shadow-raised focus-visible:outline-2 focus-visible:outline-focus">
            <span className="grid size-8 place-items-center rounded-navigation-control bg-subtle text-secondary"><MagnifyingGlass aria-hidden className="size-navigation-icon" /></span>
            <span className="min-w-0"><strong className="block truncate text-navigation-strong">{result.title}</strong><span className="mt-0.5 block truncate text-overline text-muted">{result.purpose}</span></span>
            <ArrowRight aria-hidden className="size-navigation-icon" />
          </button>
        ))}
      </div>
    </section>
  );
}

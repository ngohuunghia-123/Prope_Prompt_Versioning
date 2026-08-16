import { MagnifyingGlass, Sparkle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { cn } from '@/lib/cn';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { PromptSearchResults } from '@/features/prompt-lifecycle/components/PromptSearchResults';
import { promptSearchOptions } from '@/features/prompt-lifecycle/queries';

export function PromptSearchPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { highlight } = useAgentSurface();
  // `?q=` is how the agent hands over: it searched, and this screen runs the same
  // words rather than opening empty. A person landing here by hand has no `q`
  // and sees exactly what they saw before.
  const linked = searchParams.get('q') ?? '';
  const [draft, setDraft] = useState(linked);
  const [query, setQuery] = useState(linked);
  const [mode, setMode] = useState<'quick' | 'ai'>('quick');

  useEffect(() => {
    if (!linked) return;
    setDraft(linked);
    setQuery(linked);
  }, [linked]);

  const search = useQuery({
    ...promptSearchOptions(query, mode),
    enabled: query.trim().length > 0,
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setQuery(draft.trim());
  };

  return (
    <div className="grid gap-6 p-4 sm:p-6">
      <PageIntro
        eyebrow={t('promptSearch.results')}
        title={t('promptSearch.pageTitle')}
        description={t('promptSearch.pageDescription')}
      />

      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-end">
        <Input
          type="search"
          label={t('promptSearch.pageTitle')}
          labelHidden
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t('promptSearch.placeholder')}
          leadingIcon={<MagnifyingGlass aria-hidden className="size-4" />}
        />
        <Button
          type="button"
          intent={mode === 'ai' ? 'secondary' : 'neutral'}
          leadingIcon={<Sparkle aria-hidden className="size-4" />}
          onClick={() => setMode((current) => (current === 'ai' ? 'quick' : 'ai'))}
        >
          {mode === 'ai' ? t('promptSearch.useQuick') : t('promptSearch.searchWithAi')}
        </Button>
        <Button type="submit" loading={search.isFetching} disabled={draft.trim().length === 0}>
          {t('promptSearch.submit')}
        </Button>
      </form>

      {query.trim().length === 0 ? (
        <p className="rounded-xl border border-border bg-surface p-6 text-body text-muted shadow-panel">
          {t('promptSearch.empty')}
        </p>
      ) : (
        <div className={cn('rounded-xl transition-shadow', highlight === 'search-results' && 'ring-2 ring-secondary ring-offset-2 ring-offset-canvas')}>
        <PromptSearchResults
          results={search.data?.prompts}
          pending={search.isPending}
          error={search.isError}
          mode={mode}
          onRetry={() => void search.refetch()}
          onOpen={(promptId) => navigate(`/app/prompts/${encodeURIComponent(promptId)}`)}
        />
        </div>
      )}
    </div>
  );
}

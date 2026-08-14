import { ArrowRight, Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import type { WirePromptSearchResult } from '@/features/prompt-lifecycle/wire';

interface PromptSearchResultsProps {
  results: WirePromptSearchResult[] | undefined;
  pending: boolean;
  error: boolean;
  mode: 'quick' | 'ai';
  onRetry: () => void;
  onOpen: (promptId: string) => void;
}

export function PromptSearchResults({ results, pending, error, mode, onRetry, onOpen }: PromptSearchResultsProps) {
  const { t } = useTranslation();
  if (pending) return <QueryState state="loading" />;
  if (error) return <QueryState state="error" onRetry={onRetry} />;
  if (!results?.length) return <QueryState state="empty" />;

  return (
    <section className="grid gap-3" aria-live="polite" aria-label={t('promptSearch.results')}>
      {results.map((result) => (
        <article key={result.prompt_id} className="group rounded-xl border border-border bg-surface p-5 shadow-panel transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/60">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-heading-3 font-semibold text-ink">{result.title}</h2>
                {result.is_indexed ? <Tag state="success">{t('promptSearch.index.indexed')}</Tag> : null}
                {mode === 'ai' && result.similarity != null ? <Tag state="default"><Sparkle aria-hidden className="size-3" />{t('promptSearch.similarity', { value: Math.round(result.similarity * 100) })}</Tag> : null}
              </div>
              <p className="mt-2 text-body text-muted">{result.purpose}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {[...new Set([...result.keywords, ...result.topics])].slice(0, 8).map((term) => <Tag key={term} state="neutral">{term}</Tag>)}
              </div>
            </div>
            <Button type="button" intent="ghost" trailingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={() => onOpen(result.prompt_id)}>{t('registry.open')}</Button>
          </div>
        </article>
      ))}
    </section>
  );
}

import { Check, Copy, Lightbulb, Sparkle, Spinner, Star } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import type { PromptSuggestion } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

interface WizardSuggestionsProps {
  suggestions?: PromptSuggestion[];
  selectedId?: string;
  pending: boolean;
  error: boolean;
  onRetry: () => void;
  onSelect: (suggestion: PromptSuggestion) => void;
}

export function WizardSuggestions({ suggestions, selectedId, pending, error, onRetry, onSelect }: WizardSuggestionsProps) {
  const { t } = useTranslation();
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyPrompt = async (suggestion: PromptSuggestion) => {
    await navigator.clipboard.writeText(suggestion.promptBody);
    setCopiedId(suggestion.id);
    window.setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <span className="mx-auto mb-4 flex size-14 items-center justify-center rounded-full bg-primary/10">
          <Sparkle aria-hidden className="size-7 text-primary" weight="fill" />
        </span>
        <h2 className="font-display text-heading-2 text-ink">{t('lifecycle.wizard.suggestionsTitle')}</h2>
        <p className="mt-2 text-body text-muted">{t('lifecycle.wizard.suggestionsDescription')}</p>
      </div>

      {pending ? (
        <div role="status" className="flex flex-col items-center justify-center py-12">
          <Spinner aria-hidden className="size-8 animate-spin text-primary" />
          <p className="mt-4 text-body text-muted">{t('lifecycle.wizard.generating')}</p>
        </div>
      ) : error ? (
        <div className="rounded-modal border border-danger bg-danger/5 p-6 text-center">
          <p className="text-danger-text">{t('lifecycle.wizard.generationError')}</p>
          <Button className="mt-4" intent="secondary" size="small" onClick={onRetry}>{t('lifecycle.wizard.retry')}</Button>
        </div>
      ) : (
        <div className="space-y-4">
          {suggestions?.map((suggestion) => {
            const selected = selectedId === suggestion.id;
            return (
              <article key={suggestion.id} className={cn('rounded-modal border bg-surface p-5 shadow-panel', selected ? 'border-primary ring-2 ring-primary/20' : 'border-border')}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium text-ink">{suggestion.title}</h3>
                      <span className="inline-flex items-center gap-1 rounded-tag bg-warning/10 px-2 py-0.5 text-caption text-warning-text">
                        <Star aria-hidden className="size-3" weight="fill" />{Math.round(suggestion.confidence * 100)}%
                      </span>
                    </div>
                    <p className="mt-1 text-caption text-muted">{suggestion.explanation}</p>
                    <p className="mt-1 text-caption text-muted">{t('lifecycle.wizard.modelLabel')}: {suggestion.model}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button intent="ghost" size="icon" onClick={() => void copyPrompt(suggestion)} aria-label={t('lifecycle.wizard.copyPrompt')}>
                      {copiedId === suggestion.id ? <Check aria-hidden className="size-4 text-success-text" weight="bold" /> : <Copy aria-hidden className="size-4" />}
                    </Button>
                    <Button intent={selected ? 'primary' : 'neutral'} size="small" onClick={() => onSelect(suggestion)}>{t('lifecycle.wizard.useThis')}</Button>
                  </div>
                </div>
                {selected ? (
                  <div className="mt-4 rounded-border bg-subtle p-4">
                    <p className="flex items-center gap-2 text-caption font-medium text-muted"><Lightbulb aria-hidden className="size-4" weight="fill" />{t('lifecycle.wizard.promptPreview')}</p>
                    <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-caption text-ink">{suggestion.promptBody}</pre>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

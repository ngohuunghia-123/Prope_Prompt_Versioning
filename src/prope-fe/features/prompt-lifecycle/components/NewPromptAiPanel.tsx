import { ArrowUp, Sparkle } from '@phosphor-icons/react';
import { useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

interface NewPromptAiPanelProps {
  pending: boolean;
  error: boolean;
  applied: boolean;
  onGenerate: (idea: string) => void;
}

export function NewPromptAiPanel({ pending, error, applied, onGenerate }: NewPromptAiPanelProps) {
  const { t } = useTranslation();
  const [idea, setIdea] = useState('');

  const submit = () => {
    const normalizedIdea = idea.trim();
    if (normalizedIdea) onGenerate(normalizedIdea);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    submit();
  };

  return (
    <section aria-labelledby="new-prompt-ai-title" className="rounded-modal border border-border bg-surface p-5 shadow-panel sm:p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-full bg-accent-soft text-link"><Sparkle aria-hidden className="size-4" weight="fill" /></span>
        <div>
          <h1 id="new-prompt-ai-title" className="font-display text-heading-3 text-ink">{t('lifecycle.newPrompt.aiTitle')}</h1>
          <p className="text-caption text-muted">{t('lifecycle.newPrompt.aiDescription')}</p>
        </div>
      </div>
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <Input label={t('lifecycle.newPrompt.ideaLabel')} labelHidden value={idea} onChange={(event) => setIdea(event.target.value)} onKeyDown={handleKeyDown} placeholder={t('lifecycle.newPrompt.ideaPlaceholder')} />
        </div>
        <Button type="button" size="icon" className="size-11 min-h-11 shrink-0 rounded-lg" aria-label={t('lifecycle.newPrompt.generate')} disabled={!idea.trim()} loading={pending} onClick={submit}>
          <ArrowUp aria-hidden className="size-5" weight="bold" />
        </Button>
      </div>
      {error ? <p role="alert" className="mt-3 text-caption text-danger-text">{t('lifecycle.newPrompt.aiError')}</p> : null}
      {applied && !pending ? <p role="status" className="mt-3 text-caption text-success-text">{t('lifecycle.newPrompt.aiApplied')}</p> : null}
    </section>
  );
}

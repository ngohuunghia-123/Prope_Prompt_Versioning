import { Sparkle } from '@phosphor-icons/react';
import { useEffect, useMemo, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { Radio } from '@/components/ui/Radio';
import type { PromptSearchResult } from '@/features/prompt-lifecycle/types';

const NEW_PROMPT = '__new__';

export interface SimilarPromptsDialogProps {
  open: boolean;
  matches: PromptSearchResult[];
  sourceText: string;
  onContinue: (target: string | undefined) => void;
  onStop: () => void;
}

function words(text: string): Set<string> {
  return new Set(text.toLocaleLowerCase().match(/[\p{L}\p{N}_-]+/gu)?.filter((word) => word.length > 2) ?? []);
}

function Heatmap({ text, sharedWords }: { text: string; sharedWords: Set<string> }) {
  return (
    <p className="max-h-52 overflow-auto whitespace-pre-wrap text-caption leading-relaxed text-ink">
      {text.split(/(\s+)/).map((part, index) => (
        sharedWords.has(part.toLocaleLowerCase().replace(/[^\p{L}\p{N}_-]/gu, ''))
          ? <mark key={`${part}-${index}`} className="rounded-control bg-secondary/20 px-0.5 text-ink">{part}</mark>
          : <span key={`${part}-${index}`}>{part}</span>
      ))}
    </p>
  );
}

/** A focused comparison that helps choose between revising a match or creating a prompt. */
export function SimilarPromptsDialog({ open, matches, sourceText, onContinue, onStop }: SimilarPromptsDialogProps) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string>(NEW_PROMPT);

  useEffect(() => {
    if (open) setSelected(matches[0]?.prompt_id ?? NEW_PROMPT);
  }, [matches, open]);

  const selectedMatch = matches.find((match) => match.prompt_id === selected);
  const existingText = selectedMatch?.body_preview ?? selectedMatch?.purpose ?? '';
  const sharedWords = useMemo(() => {
    const incoming = words(sourceText);
    return new Set([...words(existingText)].filter((word) => incoming.has(word)));
  }, [existingText, sourceText]);

  return (
    <Modal
      open={open}
      title={t('lifecycle.newPrompt.similar.aiTitle')}
      description={<Trans i18nKey="lifecycle.newPrompt.similar.aiSubtitle" components={{ strong: <strong /> }} />}
      icon={<Sparkle className="size-5" weight="fill" />}
      confirmLabel={t('lifecycle.newPrompt.similar.continue')}
      onClose={onStop}
      onConfirm={() => onContinue(selected === NEW_PROMPT ? undefined : selected)}
      size="wide"
    >
      <div className="grid gap-4">
        {selectedMatch ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="rounded-xl border border-border bg-surface p-4">
              <h3 className="mb-3 text-body font-semibold text-ink">{t('lifecycle.newPrompt.similar.incomingComparison')}</h3>
              <Heatmap text={sourceText} sharedWords={sharedWords} />
            </section>
            <section className="rounded-xl border border-border bg-surface p-4">
              <h3 className="mb-3 text-body font-semibold text-ink">{t('lifecycle.newPrompt.similar.existingComparison')}</h3>
              <Heatmap text={existingText} sharedWords={sharedWords} />
            </section>
          </div>
        ) : null}

        <fieldset className="grid gap-2">
          <legend className="sr-only">{t('lifecycle.newPrompt.similar.legend')}</legend>
          {matches.map((match) => (
            <Radio key={match.prompt_id} name="prope-similar-target" value={match.prompt_id} checked={selected === match.prompt_id} onChange={() => setSelected(match.prompt_id)} label={t('lifecycle.newPrompt.similar.asNewVersion', { title: match.title })} />
          ))}
          <Radio name="prope-similar-target" value={NEW_PROMPT} checked={selected === NEW_PROMPT} onChange={() => setSelected(NEW_PROMPT)} label={t('lifecycle.newPrompt.similar.createNew')} />
        </fieldset>

        <section className="rounded-xl border border-border bg-subtle p-4">
          <h3 className="text-body font-semibold text-ink">{t('lifecycle.newPrompt.similar.aiRecommendationTitle')}</h3>
          <p className="mt-1 text-caption leading-relaxed text-muted">{t('lifecycle.newPrompt.similar.aiRecommendation')}</p>
        </section>
      </div>
    </Modal>
  );
}

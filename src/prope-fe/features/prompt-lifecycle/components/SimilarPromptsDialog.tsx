import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { Radio } from '@/components/ui/Radio';
import type { PromptSearchResult } from '@/features/prompt-lifecycle/types';

const NEW_PROMPT = '__new__';

export interface SimilarPromptsDialogProps {
  open: boolean;
  matches: PromptSearchResult[];
  /** `undefined` = import as a new prompt; a string = revise that prompt. */
  onContinue: (target: string | undefined) => void;
  onStop: () => void;
}

/** What the workspace already has that looks like the prompt being imported.
 *
 * Three outcomes, and the dialog's job is to make the middle one as easy as the
 * other two: stop, add this as a new version of something that already exists,
 * or import it as its own prompt anyway.
 *
 * The copy says what was compared. Semantic ranking covers only prompts somebody
 * indexed, so this list is never proof that nothing similar exists — and a
 * dialog that implied otherwise would be worse than no dialog, because it would
 * be trusted.
 */
export function SimilarPromptsDialog({ open, matches, onContinue, onStop }: SimilarPromptsDialogProps) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string>(NEW_PROMPT);

  return (
    <Modal
      open={open}
      title={t('lifecycle.newPrompt.similar.title', { count: matches.length })}
      description={t('lifecycle.newPrompt.similar.description')}
      confirmLabel={t('lifecycle.newPrompt.similar.continue')}
      onClose={onStop}
      onConfirm={() => onContinue(selected === NEW_PROMPT ? undefined : selected)}
      className="max-w-2xl"
    >
      <fieldset className="grid gap-3">
        <legend className="sr-only">{t('lifecycle.newPrompt.similar.legend')}</legend>
        {matches.map((match) => (
          <div key={match.prompt_id} className="rounded-xl border border-border bg-subtle p-4">
            <Radio
              name="prope-similar-target"
              value={match.prompt_id}
              checked={selected === match.prompt_id}
              onChange={() => setSelected(match.prompt_id)}
              label={t('lifecycle.newPrompt.similar.asNewVersion', { title: match.title })}
              description={match.purpose || undefined}
            />
            {typeof match.similarity === 'number' ? (
              <p className="mt-2 pl-7 text-caption text-muted">
                {t('lifecycle.newPrompt.similar.score', { percent: Math.round(match.similarity * 100) })}
                {/* An unindexed prompt was matched on wording, not meaning. Saying
                    so is the difference between a percentage somebody can weigh
                    and one they have to trust. */}
                {match.is_indexed ? null : ` · ${t('lifecycle.newPrompt.similar.roughMatch')}`}
              </p>
            ) : null}
          </div>
        ))}
        <div className="rounded-xl border border-border p-4">
          <Radio
            name="prope-similar-target"
            value={NEW_PROMPT}
            checked={selected === NEW_PROMPT}
            onChange={() => setSelected(NEW_PROMPT)}
            label={t('lifecycle.newPrompt.similar.createNew')}
            description={t('lifecycle.newPrompt.similar.createNewHint')}
          />
        </div>
      </fieldset>
      <p className="text-caption text-muted">{t('lifecycle.newPrompt.similar.indexedOnly')}</p>
    </Modal>
  );
}

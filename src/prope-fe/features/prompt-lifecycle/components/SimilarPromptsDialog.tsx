import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { Radio } from '@/components/ui/Radio';
import { Tag } from '@/components/Tag';
import type { PromptSearchResult } from '@/features/prompt-lifecycle/types';

const NEW_PROMPT = '__new__';

export interface SimilarPromptsDialogProps {
  open: boolean;
  matches: PromptSearchResult[];
  sourceText: string;
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
export function SimilarPromptsDialog({ open, matches, sourceText, onContinue, onStop }: SimilarPromptsDialogProps) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string>(NEW_PROMPT);
  const selectedMatch = matches.find((match) => match.prompt_id === selected);
  const evidenceTerms = selectedMatch
    ? [...new Set([...selectedMatch.keywords, ...selectedMatch.topics, ...selectedMatch.entities])]
        .filter((term) => sourceText.toLocaleLowerCase().includes(term.toLocaleLowerCase()))
        .slice(0, 8)
    : [];

  return (
    <Modal
      open={open}
      title={t('lifecycle.newPrompt.similar.title', { count: matches.length })}
      description={t('lifecycle.newPrompt.similar.description')}
      confirmLabel={t('lifecycle.newPrompt.similar.continue')}
      onClose={onStop}
      onConfirm={() => onContinue(selected === NEW_PROMPT ? undefined : selected)}
      size="wide"
    >
      <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.85fr)]">
      <fieldset className="grid content-start gap-3">
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
            {/* A percentage is shown only when there IS one. `similarity` is a
                cosine or it is null: a prompt found on wording alone has no
                score to report, and the term-overlap number that used to stand
                in for one reached 100% for a prompt nobody had indexed. The
                rough-match note now lives outside that branch, because it is
                exactly the case with no percentage to attach it to. */}
            {typeof match.similarity === 'number' || !match.is_indexed ? (
              <p className="mt-2 pl-7 text-caption text-muted">
                {typeof match.similarity === 'number'
                  ? t('lifecycle.newPrompt.similar.score', { percent: Math.round(match.similarity * 100) })
                  : null}
                {match.is_indexed
                  ? null
                  : `${typeof match.similarity === 'number' ? ' · ' : ''}${t('lifecycle.newPrompt.similar.roughMatch')}`}
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
      <aside className="grid content-start gap-3 rounded-xl border border-border bg-canvas p-4">
        <div>
          <h3 className="text-body font-semibold text-ink">{t('lifecycle.newPrompt.similar.evidenceTitle')}</h3>
          <p className="mt-1 text-caption text-muted">{t('lifecycle.newPrompt.similar.evidenceDescription')}</p>
        </div>
        {selectedMatch ? (
          <>
            <dl className="grid grid-cols-2 gap-2 text-caption">
              <div><dt className="text-muted">{t('lifecycle.newPrompt.similar.method')}</dt><dd className="font-medium text-ink">{selectedMatch.matched_fields.map((field) => t(`lifecycle.newPrompt.similar.methods.${field}`, { defaultValue: field })).join(' + ')}</dd></div>
              <div><dt className="text-muted">{t('lifecycle.newPrompt.similar.confidence')}</dt><dd className="font-medium text-ink">{typeof selectedMatch.similarity === 'number' ? t('lifecycle.newPrompt.similar.score', { percent: Math.round(selectedMatch.similarity * 100) }) : t('lifecycle.newPrompt.similar.roughMatch')}</dd></div>
            </dl>
            {evidenceTerms.length > 0 ? <div className="flex flex-wrap gap-1.5">{evidenceTerms.map((term) => <Tag key={term} state="neutral">{term}</Tag>)}</div> : null}
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              <section className="min-w-0 rounded-lg border border-border bg-surface p-3"><h4 className="text-caption font-semibold text-ink">{t('lifecycle.newPrompt.similar.incoming')}</h4><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-caption text-muted">{sourceText}</pre></section>
              <section className="min-w-0 rounded-lg border border-border bg-surface p-3"><h4 className="text-caption font-semibold text-ink">{t('lifecycle.newPrompt.similar.existing')}</h4><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-caption text-muted">{selectedMatch.body_preview ?? selectedMatch.purpose}</pre></section>
            </div>
          </>
        ) : <p className="text-caption text-muted">{t('lifecycle.newPrompt.similar.noEvidence')}</p>}
        <p className="text-caption text-muted">{t('lifecycle.newPrompt.similar.indexedOnly')}</p>
      </aside>
      </div>
    </Modal>
  );
}

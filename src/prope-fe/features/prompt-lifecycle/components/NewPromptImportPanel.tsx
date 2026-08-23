import { ArrowUp, FileText, Plus, Sparkle, X } from '@phosphor-icons/react';
import { useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { MAX_SOURCE_CHARACTERS, type PromptEditorValues } from '@/features/prompt-lifecycle/types';
import {
  PROMPT_SOURCE_ACCEPT,
  clearPromptSource,
  readPromptSourceFile,
  type PromptSourceFile,
  type PromptSourceFileError,
} from '@/features/prompt-lifecycle/promptSourceFile';

/**
 * Bring a prompt you already have — from a file, or from the clipboard.
 *
 * This replaced the AI draft generator that used to sit here, and took over the
 * job of the "Tôi đã có prompt" tab that used to sit inside PROMPT BODY. One bar
 * rather than a tab set, because importing is how a prompt gets into Prope and a
 * tab made it one of two equal choices.
 *
 * The box is a `textarea` and not an `input` despite being one line tall: a
 * single-line input discards newlines on paste, and a prompt body is mostly
 * newlines. Enter submits the import immediately; Shift+Enter remains available
 * when the pasted prompt needs a deliberate line break.
 */
export function NewPromptImportPanel({ onSubmitImport }: { onSubmitImport: () => void }) {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const fileRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<PromptSourceFileError | 'tooLong'>();
  // A file is attached, so the paste box has nothing to do: the two inputs are
  // exclusive, and showing an empty box beside a loaded file invites somebody to
  // type into one of them and wonder which won.
  const sourceFilename = form.watch('sourceFilename');
  const sourceText = form.watch('sourceText');

  const set = (field: 'promptBody' | 'sourceText' | 'sourceFormat' | 'sourceFilename' | 'sourceMode', value: string | undefined) => {
    form.setValue(field, value as never, { shouldDirty: true, shouldValidate: true });
  };

  /**
   * An `.xml` file is already the canonical body, so it goes straight into the
   * block editor rather than becoming a source waiting to be converted. Anything
   * else lands in `sourceText`, which is what puts the body panel into its
   * source view and what the conversion step reads.
   */
  const load = (source: PromptSourceFile) => {
    setError(undefined);
    if (source.format === 'xml') {
      set('promptBody', source.text);
      set('sourceText', '');
      set('sourceFilename', undefined);
      set('sourceFormat', 'txt');
      set('sourceMode', 'authored');
    } else {
      set('sourceText', source.text);
      set('sourceFormat', source.format);
      set('sourceFilename', source.filename);
      set('sourceMode', 'existing');
    }
    setDraft('');
  };

  const pickFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Cleared so re-picking the same file after a clear still fires `change`.
    event.target.value = '';
    if (!file) return;
    const result = await readPromptSourceFile(file);
    if (typeof result === 'string') {
      setError(result);
      return;
    }
    load(result);
  };

  const submitDraft = () => {
    const text = draft.trim();
    if (!text) return;
    if (draft.length > MAX_SOURCE_CHARACTERS) {
      setError('tooLong');
      return;
    }
    // Pasted text has no filename and no extension to read a format from, so it
    // is `txt` — which is what the converter treats prose as anyway.
    load({ text: draft, format: 'txt', filename: '' });
    onSubmitImport();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitDraft();
    }
  };

  const errorText = error === 'tooLong'
    ? t('lifecycle.newPrompt.source.errors.tooLong')
    : error
      ? t(`lifecycle.newPrompt.source.${error}`)
      : undefined;

  return (
    <section aria-labelledby="new-prompt-import-title" className="rounded-modal border border-border bg-surface p-5 shadow-panel sm:p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-full bg-accent-soft text-link">
          <Sparkle aria-hidden className="size-4" weight="fill" />
        </span>
        <div>
          <h1 id="new-prompt-import-title" className="font-display text-heading-3 text-ink">{t('lifecycle.newPrompt.importTitle')}</h1>
          <p className="text-caption text-muted">{t('lifecycle.newPrompt.importDescription')}</p>
        </div>
      </div>

      <div className="flex items-start gap-2">
        <Button
          type="button"
          intent="neutral"
          size="icon"
          className="size-11 min-h-11 shrink-0 rounded-lg"
          aria-label={t('lifecycle.newPrompt.source.uploadAction')}
          title={t('lifecycle.newPrompt.source.uploadHint')}
          onClick={() => fileRef.current?.click()}
        >
          <Plus aria-hidden className="size-5" weight="bold" />
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept={PROMPT_SOURCE_ACCEPT}
          onChange={(event) => void pickFile(event)}
          className="sr-only"
          tabIndex={-1}
        />
        {sourceFilename ? (
          <>
            <div className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-subtle px-3 shadow-inset">
              <FileText aria-hidden className="size-5 shrink-0 text-muted" />
              <span className="truncate text-body font-medium text-ink">{sourceFilename}</span>
              <span className="shrink-0 text-caption text-muted">
                {t('lifecycle.newPrompt.source.characters', { count: sourceText.length })}
              </span>
            </div>
            <Button
              type="button"
              intent="neutral"
              size="icon"
              className="size-11 min-h-11 shrink-0 rounded-lg"
              aria-label={t('lifecycle.newPrompt.source.clear')}
              onClick={() => { clearPromptSource(form); setError(undefined); }}
            >
              <X aria-hidden className="size-5" weight="bold" />
            </Button>
          </>
        ) : (
          <>
            <textarea
              rows={5}
              value={draft}
              onChange={(event) => { setDraft(event.target.value); setError(undefined); }}
              onKeyDown={onKeyDown}
              spellCheck={false}
              aria-label={t('lifecycle.newPrompt.pasteLabel')}
              placeholder={t('lifecycle.newPrompt.pastePlaceholder')}
              className="min-h-32 min-w-0 flex-1 resize-y overflow-y-auto rounded-lg border border-border bg-surface px-3 py-3 text-body text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25"
            />
            <Button
              type="button"
              size="icon"
              className="size-11 min-h-11 shrink-0 rounded-lg"
              aria-label={t('lifecycle.newPrompt.importAction')}
              disabled={!draft.trim()}
              onClick={submitDraft}
            >
              <ArrowUp aria-hidden className="size-5" weight="bold" />
            </Button>
          </>
        )}
      </div>

      {errorText ? <p role="alert" className="mt-3 text-caption text-danger-text">{errorText}</p> : null}
    </section>
  );
}

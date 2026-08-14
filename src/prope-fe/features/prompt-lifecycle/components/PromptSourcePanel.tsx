import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Textarea } from '@/components/ui/Textarea';
import { PromptSourceUpload, type PromptSourceFile } from '@/features/prompt-lifecycle/components/PromptSourceUpload';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

/** Upload a prompt or paste one — one or the other, never both at once.
 *
 * Both write the same three fields (`sourceText`, `sourceFormat`,
 * `sourceFilename`), so there is exactly one text the rest of the flow can read
 * and no reconciliation step anywhere. `sourceFilename` being set is what marks
 * the text as having come from a file, and it is what disables the textarea; a
 * non-empty textarea disables the upload in the other direction. If both were
 * ever populated the file would win, because the file is what set `sourceText`
 * last — but the disabling is what makes that unreachable rather than merely
 * decided.
 */
export function PromptSourcePanel() {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const sourceText = form.watch('sourceText');
  const sourceFilename = form.watch('sourceFilename');
  const fromFile = Boolean(sourceFilename);

  const set = (field: 'sourceText' | 'sourceFormat' | 'sourceFilename', value: string | undefined) => {
    form.setValue(field, value as never, { shouldDirty: true, shouldValidate: true });
  };

  const loadFile = (file: PromptSourceFile) => {
    set('sourceText', file.text);
    set('sourceFormat', file.format);
    set('sourceFilename', file.filename);
  };

  const clearFile = () => {
    set('sourceText', '');
    set('sourceFormat', 'txt');
    set('sourceFilename', undefined);
  };

  // `tooShort` / `tooLong` are the only two messages `promptEditorSchema`'s
  // superRefine puts on this field, so the key is bounded even though it is
  // built from a value.
  const issue = form.formState.errors.sourceText?.message;
  const error = issue ? t(`lifecycle.newPrompt.source.errors.${issue}`) : undefined;

  return (
    <section aria-labelledby="prompt-source-title" className="grid gap-4">
      <div>
        <h3 id="prompt-source-title" className="text-body font-semibold text-ink">
          {t('lifecycle.newPrompt.source.title')}
        </h3>
        <p className="mt-1 text-caption text-muted">{t('lifecycle.newPrompt.source.description')}</p>
      </div>

      <PromptSourceUpload
        filename={sourceFilename}
        disabled={!fromFile && sourceText.trim().length > 0}
        onLoad={loadFile}
        onClear={clearFile}
      />

      <Textarea
        className="min-h-64 font-mono"
        label={t('lifecycle.newPrompt.source.pasteLabel')}
        placeholder={t('lifecycle.newPrompt.source.pastePlaceholder')}
        hint={fromFile ? t('lifecycle.newPrompt.source.pasteDisabled') : undefined}
        error={error}
        disabled={fromFile}
        spellCheck={false}
        // Shows the uploaded text rather than blanking, so somebody can see
        // WHICH file they picked before committing to importing it. Read-only
        // via `disabled`, which is what keeps the two inputs exclusive.
        value={sourceText}
        onChange={(event) => {
          set('sourceText', event.target.value);
          set('sourceFormat', 'txt');
        }}
      />
    </section>
  );
}

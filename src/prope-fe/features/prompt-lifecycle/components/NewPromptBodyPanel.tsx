import { FileText, X } from '@phosphor-icons/react';
import { Controller, useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';
import { XmlBlockEditor } from '@/features/prompt-lifecycle/components/XmlBlockEditor';
import { clearPromptSource } from '@/features/prompt-lifecycle/promptSourceFile';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

/**
 * What the source looks like between importing it and converting it.
 *
 * Read-only, because editing it here would fork the text the conversion step is
 * about to read. Removing it is the way back to authoring — and it is a clear
 * rather than an undo: the body panel shows one body, and this is it.
 */
function ImportedSourceView() {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const sourceText = form.watch('sourceText');
  const sourceFilename = form.watch('sourceFilename');

  // `tooShort` / `tooLong` are the only two messages `promptEditorSchema`'s
  // superRefine puts on this field, so the key is bounded even though it is
  // built from a value.
  const issue = form.formState.errors.sourceText?.message;

  return (
    <section aria-labelledby="imported-source-title" className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-subtle px-4 py-3">
        <span className="flex min-w-0 items-center gap-2 text-body text-ink">
          <FileText aria-hidden className="size-5 shrink-0 text-muted" />
          <span id="imported-source-title" className="truncate font-medium">
            {sourceFilename || t('lifecycle.newPrompt.source.pasted')}
          </span>
          <span className="shrink-0 text-caption text-muted">
            {t('lifecycle.newPrompt.source.characters', { count: sourceText.length })}
          </span>
        </span>
        <Button type="button" intent="neutral" size="small" leadingIcon={<X aria-hidden className="size-4" />} onClick={() => clearPromptSource(form)}>
          {t('lifecycle.newPrompt.source.clear')}
        </Button>
      </div>

      <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-surface p-4 font-mono text-caption text-ink shadow-inset">
        {sourceText}
      </pre>

      {issue ? (
        <p role="alert" className="text-caption text-danger-text">{t(`lifecycle.newPrompt.source.errors.${issue}`)}</p>
      ) : (
        <p className="text-caption text-muted">{t('lifecycle.newPrompt.source.pendingConversion')}</p>
      )}
    </section>
  );
}

/**
 * The one body on the screen.
 *
 * It used to be two tabs — "Tôi đã có prompt" and "Tôi muốn tạo prompt mới" —
 * with `sourceMode` as the selected tab. Importing now happens in its own panel
 * above, so `sourceMode` is no longer chosen by anybody: a loaded source makes it
 * `existing`, clearing one makes it `authored`, and a finished conversion makes
 * it `authored` again with the blocks in place. This panel just renders whichever
 * of the two the form is currently in, which is what makes the heading true.
 */
export function NewPromptBodyPanel() {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const sourceMode = form.watch('sourceMode');

  return (
    <Card title={t('lifecycle.newPrompt.promptBody')} description={t('lifecycle.editor.promptBodyHint')} className="min-h-full">
      {sourceMode === 'existing' ? (
        <ImportedSourceView />
      ) : (
        <Controller
          name="promptBody"
          control={form.control}
          render={({ field, fieldState }) => (
            <XmlBlockEditor value={field.value} onChange={field.onChange} error={fieldState.error ? t('lifecycle.xml.errors.malformed') : undefined} />
          )}
        />
      )}
    </Card>
  );
}

import { useEffect, useId, useState } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Tooltip } from '@/components/ui/Tooltip';
import { ProviderBindingFields } from '@/features/prompt-lifecycle/components/ProviderBindingFields';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { slugify } from '@/lib/slugify';

/**
 * The model name, as a fixed folder prefix and a name somebody types.
 *
 * The namespace is not an input. It is the folder this composer was opened from,
 * it is in the URL, and A-021 makes the pair immutable the moment the prompt
 * exists — so a field that could be edited into a different folder would be a
 * field that silently files the prompt somewhere the page does not say. The
 * prefix renders inside the same bordered box as the name, because
 * `marketing/tro-ly-thanh-toan` is one identifier and reading it as two would
 * suggest they can move independently.
 */
function ModelNameField() {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const namespace = form.watch('namespace');
  const title = form.watch('title');
  // Once the name has been typed in, the title stops driving it. Same rule as
  // the folder dialog's name → slug, and for the same reason: the fold is a
  // defensible default, not a decision.
  const [nameTouched, setNameTouched] = useState(false);
  const fieldId = useId();
  const labelId = `${fieldId}-label`;
  const hintId = `${fieldId}-hint`;

  // **The guard is what stops this from freezing the tab, and it is not
  // cosmetic.** `useFormContext` hands back a fresh object on every render —
  // `FormProvider` spreads its props into the context value — so `form` in the
  // dependency list makes this effect run after *every* render. That was
  // harmless until the first submit, at which point `isSubmitted` turns
  // `shouldValidate` on: the write then runs the resolver, the resolver
  // publishes `errors`, publishing re-renders every subscriber, and the
  // re-render runs this effect again. Pressing "Đánh giá" started an infinite
  // render loop and locked the page. Writing only when the fold actually
  // differs breaks it — the second pass finds the value already there and
  // stops — and it is the honest condition anyway: this effect exists to keep
  // the name in step with the title, not to rewrite it with itself.
  useEffect(() => {
    if (nameTouched) return;
    const folded = slugify(title);
    if (folded === form.getValues('name')) return;
    form.setValue('name', folded, { shouldValidate: form.formState.isSubmitted });
  }, [form, nameTouched, title]);

  const invalid = Boolean(form.formState.errors.name);
  const nameField = form.register('name', { onChange: () => setNameTouched(true) });

  return (
    <div className="flex min-w-0 flex-col gap-2 text-body font-medium text-ink">
      <span id={labelId}>{t('lifecycle.editor.modelName')}</span>
      <div
        className={`flex h-11 items-stretch overflow-hidden rounded-lg border bg-surface shadow-inset transition-colors duration-(--prope-motion-duration-fast) focus-within:ring-2 ${
          invalid
            ? 'border-danger-strong focus-within:border-danger-strong focus-within:ring-danger-strong/25'
            : 'border-border focus-within:border-focus focus-within:ring-focus/25'
        }`}
      >
        <Tooltip label={`${namespace}/`} side="right" className="min-w-0 max-w-1/2">
          <span tabIndex={0} className="flex min-w-0 flex-1 items-center truncate border-r border-border bg-subtle px-3 font-mono text-body font-normal text-muted focus-visible:outline-2 focus-visible:outline-focus">
            {namespace}/
          </span>
        </Tooltip>
        <input
          {...nameField}
          aria-labelledby={labelId}
          aria-invalid={invalid}
          aria-describedby={hintId}
          spellCheck={false}
          placeholder={t('lifecycle.editor.namePlaceholder')}
          className="min-w-0 flex-1 cursor-text bg-transparent px-3 font-mono text-body font-normal text-ink outline-none placeholder:font-sans placeholder:text-muted"
        />
      </div>
      <span id={hintId} className={`text-caption font-normal ${invalid ? 'text-danger-text' : 'text-muted'}`}>
        {invalid ? t('lifecycle.editor.nameInvalid') : t('lifecycle.editor.nameHint')}
      </span>
    </div>
  );
}

export function NewPromptMetadataPanel() {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const errorFor = (name: keyof PromptEditorValues) => form.formState.errors[name] ? t('lifecycle.validation.required') : undefined;
  const accessOptions = [{ value: 'private', label: t('lifecycle.access.private') }, { value: 'workspace', label: t('lifecycle.access.workspace') }];

  return (
    <Card title={t('lifecycle.newPrompt.metadata')}>
      <Input label={t('lifecycle.editor.title')} error={errorFor('title')} {...form.register('title')} />
      <ModelNameField />
      <Controller name="access" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.access')} options={accessOptions} value={field.value} onValueChange={field.onChange} />} />
      <ProviderBindingFields />
      <Textarea className="min-h-24" label={t('lifecycle.editor.fallbackAnswer')} error={errorFor('fallbackAnswer')} {...form.register('fallbackAnswer')} />
      <Textarea className="min-h-24" label={t('lifecycle.editor.changeSummary')} error={errorFor('changeSummary')} {...form.register('changeSummary')} />
    </Card>
  );
}

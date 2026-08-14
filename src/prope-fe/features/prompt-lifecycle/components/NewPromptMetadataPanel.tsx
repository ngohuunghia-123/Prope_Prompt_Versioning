import { Controller, useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

export function NewPromptMetadataPanel() {
  const { t } = useTranslation();
  const form = useFormContext<PromptEditorValues>();
  const errorFor = (name: keyof PromptEditorValues) => form.formState.errors[name] ? t('lifecycle.validation.required') : undefined;
  const accessOptions = [{ value: 'private', label: t('lifecycle.access.private') }, { value: 'workspace', label: t('lifecycle.access.workspace') }];
  const providerOptions = [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }];

  return (
    <Card title={t('lifecycle.newPrompt.metadata')} className="min-h-full">
      <Input label={t('lifecycle.editor.title')} error={errorFor('title')} {...form.register('title')} />
      <Input label={t('lifecycle.editor.modelName')} hint={t('lifecycle.editor.modelNameHint')} error={errorFor('modelName')} {...form.register('modelName')} />
      <Controller name="access" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.access')} options={accessOptions} value={field.value} onValueChange={field.onChange} />} />
      <Controller name="provider" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.provider')} options={providerOptions} value={field.value} onValueChange={field.onChange} />} />
      <Input label={t('lifecycle.editor.providerModel')} error={errorFor('providerModel')} {...form.register('providerModel')} />
      <Textarea className="min-h-24" label={t('lifecycle.editor.fallbackAnswer')} error={errorFor('fallbackAnswer')} {...form.register('fallbackAnswer')} />
      <Textarea className="min-h-24" label={t('lifecycle.editor.changeSummary')} error={errorFor('changeSummary')} {...form.register('changeSummary')} />
    </Card>
  );
}

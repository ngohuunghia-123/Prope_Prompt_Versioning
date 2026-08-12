import { zodResolver } from '@hookform/resolvers/zod';
import { CheckCircle, Flask, FloppyDisk, Play } from '@phosphor-icons/react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { XmlBlockEditor } from '@/features/prompt-lifecycle/components/XmlBlockEditor';
import { useSavePromptMutation, useStartEvaluationMutation } from '@/features/prompt-lifecycle/queries';
import { promptEditorSchema, type PromptEditorValues } from '@/features/prompt-lifecycle/types';

export interface PromptEditorFormProps { initialValues: PromptEditorValues; promptId: string; editing?: boolean; }

export function PromptEditorForm({ initialValues, promptId, editing = false }: PromptEditorFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const saveMutation = useSavePromptMutation();
  const evaluationMutation = useStartEvaluationMutation(promptId);
  const form = useForm<PromptEditorValues>({ resolver: zodResolver(promptEditorSchema), defaultValues: initialValues });
  const fieldError = (name: keyof PromptEditorValues) => form.formState.errors[name] ? t('lifecycle.validation.required') : undefined;
  const save = form.handleSubmit((values) => saveMutation.mutate(values, { onSuccess: () => void navigate(`/app/prompts/${promptId}`) }));
  const evaluate = form.handleSubmit((values) => evaluationMutation.mutate(values, { onSuccess: () => void navigate(`/app/prompts/${promptId}`) }));
  const pending = saveMutation.isPending || evaluationMutation.isPending;
  const accessOptions = [{ value: 'private', label: t('lifecycle.access.private') }, { value: 'workspace', label: t('lifecycle.access.workspace') }];
  const providerOptions = [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }];
  return (
    <form className="grid gap-6" onSubmit={(event) => void evaluate(event)}>
      <PageIntro eyebrow={t('lifecycle.editor.eyebrow')} title={t(editing ? 'lifecycle.editor.editTitle' : 'lifecycle.editor.registerTitle')} description={t('lifecycle.editor.description')} />
      {saveMutation.isError || evaluationMutation.isError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{t(evaluationMutation.isError ? 'lifecycle.editor.evaluationError' : 'lifecycle.editor.saveError')}</Notification> : null}
      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="gap-5 xl:col-span-2" title={t('lifecycle.editor.promptDetails')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label={t('lifecycle.editor.title')} error={fieldError('title')} {...form.register('title')} />
            <Input label={t('lifecycle.editor.modelName')} hint={t('lifecycle.editor.modelNameHint')} error={fieldError('modelName')} {...form.register('modelName')} />
            <Controller name="access" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.access')} options={accessOptions} value={field.value} onValueChange={field.onChange} />} />
            <Controller name="provider" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.provider')} options={providerOptions} value={field.value} onValueChange={field.onChange} />} />
            <Input label={t('lifecycle.editor.providerModel')} error={fieldError('providerModel')} {...form.register('providerModel')} />
          </div>
          <Controller name="promptBody" control={form.control} render={({ field, fieldState }) => <XmlBlockEditor value={field.value} onChange={field.onChange} error={fieldState.error ? t('lifecycle.xml.errors.malformed') : undefined} />} />
          <Textarea label={t('lifecycle.editor.fallbackAnswer')} error={fieldError('fallbackAnswer')} {...form.register('fallbackAnswer')} />
          <Textarea className="min-h-24" label={t('lifecycle.editor.changeSummary')} error={fieldError('changeSummary')} {...form.register('changeSummary')} />
        </Card>
        <div className="grid content-start gap-6">
          <Card title={t('lifecycle.editor.evalSuite')}><div className="mt-3 grid gap-3">{['safety', 'accuracy', 'format'].map((suite) => <div key={suite} className="flex items-center justify-between rounded-lg border border-border bg-subtle p-3"><span className="flex items-center gap-2 text-ink"><Flask aria-hidden className="size-4 text-secondary" />{t(`lifecycle.editor.suites.${suite}`)}</span><span className="text-caption font-semibold text-success-text">{t('lifecycle.editor.caseCount', { count: suite === 'safety' ? 12 : 10 })}</span></div>)}</div><p className="mt-4 flex items-start gap-2 text-caption text-muted"><CheckCircle aria-hidden className="mt-0.5 size-4 shrink-0 text-success-strong" />{t('lifecycle.editor.evalNote')}</p></Card>
          <Card title={t('lifecycle.editor.versionTitle')}><p>{t('lifecycle.editor.versionDescription')}</p></Card>
        </div>
      </div>
      <div className="sticky bottom-4 flex flex-wrap justify-end gap-3 rounded-xl border border-border bg-surface/95 p-4 shadow-floating backdrop-blur-sm">
        <Button type="button" intent="neutral" disabled={pending} leadingIcon={<FloppyDisk aria-hidden className="size-4" />} loading={saveMutation.isPending} onClick={() => void save()}>{t('lifecycle.editor.saveDraft')}</Button>
        <Button type="submit" disabled={pending} leadingIcon={<Play aria-hidden className="size-4" />} loading={evaluationMutation.isPending}>{t(evaluationMutation.isPending ? 'lifecycle.editor.startingEvaluation' : 'lifecycle.editor.evaluate')}</Button>
      </div>
    </form>
  );
}

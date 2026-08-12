import { CaretDown, CaretUp, FloppyDisk, Play } from '@phosphor-icons/react';
import { zodResolver } from '@hookform/resolvers/zod';
import { createPortal } from 'react-dom';
import { Controller, useForm } from 'react-hook-form';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { PromptTestPanel } from '@/features/prompt-lifecycle/components/PromptTestPanel';
import { XmlBlockEditor } from '@/features/prompt-lifecycle/components/XmlBlockEditor';
import { useSavePromptMutation, useStartEvaluationMutation } from '@/features/prompt-lifecycle/queries';
import { promptEditorSchema, type PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { extractTemplateTokens, parseXmlBlocks } from '@/features/prompt-lifecycle/xmlBlocks';

export interface PromptEditorFormProps { initialValues: PromptEditorValues; promptId: string; editing?: boolean; }

export function PromptEditorForm({ initialValues, promptId, editing = false }: PromptEditorFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [contentExpanded, setContentExpanded] = useState(true);
  const saveMutation = useSavePromptMutation();
  const evaluationMutation = useStartEvaluationMutation(promptId);
  const form = useForm<PromptEditorValues>({ resolver: zodResolver(promptEditorSchema), defaultValues: initialValues });
  const fieldError = (name: keyof PromptEditorValues) => form.formState.errors[name] ? t('lifecycle.validation.required') : undefined;
  const save = form.handleSubmit((values) => saveMutation.mutate(values, { onSuccess: () => void navigate(`/app/prompts/${promptId}`) }));
  const evaluate = form.handleSubmit((values) => evaluationMutation.mutate(values, { onSuccess: () => void navigate(`/app/prompts/${promptId}`) }));
  const pending = saveMutation.isPending || evaluationMutation.isPending;
  const accessOptions = [{ value: 'private', label: t('lifecycle.access.private') }, { value: 'workspace', label: t('lifecycle.access.workspace') }];
  const providerOptions = [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }];
  const promptBody = form.watch('promptBody');
  const parsed = parseXmlBlocks(promptBody);
  const blocks = parsed.success ? parsed.blocks.length : 0;
  const templateVariables = extractTemplateTokens(promptBody).map((token) => token.slice(2, -2).trim());
  const variables = templateVariables.length;
  const actions = <><Button type="button" intent="ghost" disabled={pending} leadingIcon={<FloppyDisk aria-hidden className="size-5" />} loading={saveMutation.isPending} onClick={() => void save()}>{t('lifecycle.editor.saveDraft')}</Button><Button type="submit" form="prompt-editor-form" disabled={pending} leadingIcon={<Play aria-hidden className="size-5" />} loading={evaluationMutation.isPending}>{t(evaluationMutation.isPending ? 'lifecycle.editor.startingEvaluation' : 'lifecycle.editor.evaluate')}</Button></>;
  const actionTarget = document.getElementById('topbar-actions');
  return <form id="prompt-editor-form" className="grid gap-6 pb-16 xl:pb-0" onSubmit={(event) => void evaluate(event)}>
    {actionTarget ? createPortal(actions, actionTarget) : null}
    <PageIntro eyebrow={t('lifecycle.editor.eyebrow')} title={t(editing ? 'lifecycle.editor.editTitle' : 'lifecycle.editor.registerTitle')} description={t('lifecycle.editor.description')} />
    {saveMutation.isError || evaluationMutation.isError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{t(evaluationMutation.isError ? 'lifecycle.editor.evaluationError' : 'lifecycle.editor.saveError')}</Notification> : null}
    <div className="grid gap-6 xl:grid-cols-3">
      <div className="grid content-start gap-6 xl:col-span-2">
        <Card title={t('lifecycle.editor.promptMetadata')}>
          <div className="grid gap-5 sm:grid-cols-2"><Input label={t('lifecycle.editor.title')} error={fieldError('title')} {...form.register('title')} /><Input label={t('lifecycle.editor.modelName')} hint={t('lifecycle.editor.modelNameHint')} error={fieldError('modelName')} {...form.register('modelName')} /><Controller name="access" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.access')} options={accessOptions} value={field.value} onValueChange={field.onChange} />} /><Controller name="provider" control={form.control} render={({ field }) => <Select label={t('lifecycle.editor.provider')} options={providerOptions} value={field.value} onValueChange={field.onChange} />} /><Input label={t('lifecycle.editor.providerModel')} error={fieldError('providerModel')} {...form.register('providerModel')} /></div>
        </Card>
        <Card title={undefined}>
          <div className="flex items-center justify-between gap-3"><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.editor.promptDetails')}</h2><button type="button" onClick={() => setContentExpanded((value) => !value)} aria-expanded={contentExpanded} className="flex cursor-pointer items-center gap-2 text-caption font-medium text-link focus-visible:outline-2 focus-visible:outline-focus">{contentExpanded ? <CaretUp aria-hidden className="size-5" /> : <CaretDown aria-hidden className="size-5" />}{contentExpanded ? t('lifecycle.editor.collapse') : t('lifecycle.editor.expand')}</button></div>
          {!contentExpanded ? <p className="text-caption text-muted">{t('lifecycle.editor.collapsedSummary', { blocks, variables })}</p> : <div className="grid gap-6">
          <Controller name="promptBody" control={form.control} render={({ field, fieldState }) => <XmlBlockEditor value={field.value} onChange={field.onChange} error={fieldState.error ? t('lifecycle.xml.errors.malformed') : undefined} />} />
          <div className="grid gap-5"><Textarea label={t('lifecycle.editor.fallbackAnswer')} error={fieldError('fallbackAnswer')} {...form.register('fallbackAnswer')} /><Textarea className="min-h-24" label={t('lifecycle.editor.changeSummary')} error={fieldError('changeSummary')} {...form.register('changeSummary')} /></div>
          </div>}
        </Card>
      </div>
      <PromptTestPanel variables={templateVariables} />
    </div>
  </form>;
}

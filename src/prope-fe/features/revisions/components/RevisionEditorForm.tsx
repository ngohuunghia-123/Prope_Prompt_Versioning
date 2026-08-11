import { zodResolver } from '@hookform/resolvers/zod';
import { FloppyDisk } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { revisionFormSchema, type RevisionFormValues } from '@/features/revisions/types';

interface RevisionEditorFormProps {
  promptId: string;
  initialValues: Omit<RevisionFormValues, 'summary'>;
  saving: boolean;
  onSave: (values: RevisionFormValues) => void;
}

export function RevisionEditorForm({ promptId, initialValues, saving, onSave }: RevisionEditorFormProps) {
  const { t } = useTranslation();
  const { register, handleSubmit, formState: { errors } } = useForm<RevisionFormValues>({
    resolver: zodResolver(revisionFormSchema),
    defaultValues: { ...initialValues, summary: '' },
  });
  return (
    <form onSubmit={handleSubmit(onSave)} className="space-y-5 rounded-panel border border-border bg-surface p-5 shadow-floating sm:p-8">
      <div><p className="text-overline font-semibold text-muted">{t('revisions.editor.eyebrow')}</p><h1 className="mt-2 text-heading-1 font-semibold">{t('revisions.editor.title')}</h1><p className="mt-2 text-body text-muted">{t('revisions.editor.description')}</p></div>
      <Textarea label={t('revisions.editor.content')} hint={t('revisions.editor.contentHint')} error={errors.content ? t('revisions.validation.content') : undefined} rows={14} {...register('content')} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label={t('revisions.editor.providerName')} error={errors.providerName ? t('revisions.validation.providerName') : undefined} {...register('providerName')} />
        <Input label={t('revisions.editor.upstreamModel')} error={errors.upstreamModel ? t('revisions.validation.upstreamModel') : undefined} {...register('upstreamModel')} />
        <Input type="number" step="0.1" label={t('revisions.editor.temperature')} error={errors.temperature ? t('revisions.validation.temperature') : undefined} {...register('temperature', { valueAsNumber: true })} />
        <Input type="number" label={t('revisions.editor.maxTokens')} error={errors.maxTokens ? t('revisions.validation.maxTokens') : undefined} {...register('maxTokens', { valueAsNumber: true })} />
      </div>
      <Textarea label={t('revisions.editor.fallbackAnswer')} error={errors.fallbackAnswer ? t('revisions.validation.fallbackAnswer') : undefined} rows={3} {...register('fallbackAnswer')} />
      <Input label={t('revisions.editor.summary')} placeholder={t('revisions.editor.summaryPlaceholder')} hint={t('revisions.editor.summaryHint')} error={errors.summary ? t('revisions.validation.summary') : undefined} {...register('summary')} />
      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-5">
        <Link to={`/app/prompts/${promptId}`} className="inline-flex min-h-10 items-center rounded-xl border border-border bg-surface px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus">{t('common.cancel')}</Link>
        <Button type="submit" loading={saving} leadingIcon={<FloppyDisk aria-hidden className="size-4" />}>{t('revisions.actions.save')}</Button>
      </div>
    </form>
  );
}

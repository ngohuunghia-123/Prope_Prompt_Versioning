import { zodResolver } from '@hookform/resolvers/zod';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useCreateImportBatch } from '@/features/prompt-ingestion/queries';
import { uploadFormSchema, type UploadFormValues } from '@/features/prompt-ingestion/types';

export function ImportUploadPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const mutation = useCreateImportBatch();
  const form = useForm<UploadFormValues>({
    resolver: zodResolver(uploadFormSchema),
    defaultValues: { namespace: 'workspace', mode: 'files', accessLevel: 'private' },
  });
  const submit = form.handleSubmit(async (values) => {
    const batch = await mutation.mutateAsync(values);
    void navigate(`/app/imports/${batch.id}`);
  });
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-4 sm:p-6 lg:p-8">
      <header className="space-y-2">
        <h1 className="text-heading-1 font-semibold text-ink">{t('ingestion.upload.title')}</h1>
        <p className="text-body text-muted">{t('ingestion.upload.description')}</p>
      </header>
      <form className="grid gap-5 rounded-card border border-border bg-surface p-5 shadow-card" onSubmit={submit}>
        <Input label={t('ingestion.upload.namespace')} error={form.formState.errors.namespace?.message ? t('ingestion.upload.invalidNamespace') : undefined} {...form.register('namespace')} />
        <Controller control={form.control} name="mode" render={({ field }) => <Select label={t('ingestion.upload.mode')} value={field.value} onValueChange={field.onChange} options={[{ value: 'files', label: t('ingestion.upload.filesMode') }, { value: 'table', label: t('ingestion.upload.tableMode') }]} />} />
        <Controller control={form.control} name="accessLevel" render={({ field }) => <Select label={t('ingestion.upload.access')} value={field.value} onValueChange={field.onChange} options={[{ value: 'private', label: t('ingestion.upload.private') }, { value: 'workspace', label: t('ingestion.upload.workspace') }]} />} />
        <Input type="file" multiple accept=".txt,.md,.json,.yaml,.yml,.csv,.xlsx,.zip" label={t('ingestion.upload.files')} hint={t('ingestion.upload.fileHint')} error={form.formState.errors.files ? t('ingestion.upload.filesRequired') : undefined} {...form.register('files')} />
        {mutation.isError ? <p role="alert" className="text-body text-danger-text">{t('ingestion.upload.failed')}</p> : null}
        <Button type="submit" loading={mutation.isPending}>{t('ingestion.upload.start')}</Button>
      </form>
    </main>
  );
}

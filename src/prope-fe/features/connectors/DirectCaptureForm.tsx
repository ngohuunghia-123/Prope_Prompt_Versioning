import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { getFolders } from '@/features/connectors/api';
import { callHost } from '@/features/connectors/bridge';
import { directCaptureSchema } from '@/features/connectors/directContracts';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { isCanonicalXml } from '@/features/prompt-lifecycle/xmlBlocks';

const captureFormSchema = directCaptureSchema.superRefine((value, context) => {
  if (value.format === 'xml' && !isCanonicalXml(value.source)) context.addIssue({ code: 'custom', path: ['source'], message: 'invalid_canonical_xml' });
});

export function DirectCaptureForm() {
  const { t } = useTranslation();
  const folders = useQuery({ queryKey: ['connector', 'folders'], queryFn: getFolders });
  const form = useForm<z.input<typeof directCaptureSchema>, unknown, z.output<typeof directCaptureSchema>>({ resolver: zodResolver(captureFormSchema), defaultValues: { namespace: '', source: '', format: 'markdown' } });
  const stage = useMutation({ mutationFn: (input: z.output<typeof directCaptureSchema>) => callHost('capture_direct', input), onSuccess: () => form.resetField('source') });
  return <form className="space-y-3 rounded-lg border border-border bg-surface p-4" onSubmit={form.handleSubmit((value) => stage.mutate(value))}>
    <h2 className="font-display text-heading-3">{t('connector.directTitle')}</h2>
    <p className="text-caption text-muted">{t('connector.directHint')}</p>
    {folders.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {folders.data?.length === 0 ? <p>{t('connector.noFolders')}</p> : null}
    <Controller control={form.control} name="namespace" render={({ field, fieldState }) => <Select label={t('connector.namespace')} value={field.value} onValueChange={field.onChange}
      options={[{ value: '', label: t('connector.choose') }, ...(folders.data ?? []).map((folder) => ({ value: folder.slug, label: folder.name }))]} error={fieldState.error ? t('connector.invalid') : undefined} />} />
    <Controller control={form.control} name="format" render={({ field }) => <Select label={t('connector.sourceFormat')} value={field.value} onValueChange={field.onChange}
      options={['markdown', 'txt', 'xml'].map((format) => ({ value: format, label: t(`connector.formats.${format}`) }))} />} />
    <p className="text-caption text-muted">{t('connector.sourceFormatHint')}</p>
    <Textarea label={t('connector.original')} rows={8} {...form.register('source')} error={form.formState.errors.source ? t(form.formState.errors.source.message === 'invalid_canonical_xml' ? 'connector.invalidCanonicalXml' : 'connector.invalid') : undefined} />
    <ConnectorError error={folders.error ?? stage.error} />
    <Button type="submit" loading={stage.isPending} disabled={!folders.data?.length}>{t('connector.continueEditing')}</Button>
    {stage.isSuccess ? <p role="status">{t('connector.proposalReady')}</p> : null}
  </form>;
}

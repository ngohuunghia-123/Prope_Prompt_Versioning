import { Controller } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { useOpenRevisionForm } from '@/features/connectors/useOpenRevisionForm';
import { revisionTargetSchema } from '@/features/connectors/directContracts';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function OpenRevisionForm({ onOpen, initialPromptId = '' }: { onOpen: (target: z.infer<typeof revisionTargetSchema>) => void; initialPromptId?: string }) {
  const { t } = useTranslation();
  const { form, promptId, prompts, revisions, canOpen } = useOpenRevisionForm(initialPromptId);
  return <form className="space-y-3 rounded-lg border border-border bg-surface p-4" onSubmit={form.handleSubmit((target) => { if (canOpen) onOpen(target); })}>
    <h2 className="font-display text-heading-3">{t('connector.openExisting')}</h2>
    {prompts.isPending || (promptId && revisions.isPending) ? <p role="status">{t('common.loading')}</p> : null}
    {prompts.data?.length === 0 ? <p>{t('connector.noPrompts')}</p> : null}
    <Controller control={form.control} name="prompt_id" render={({ field, fieldState }) => <Select label={t('connector.target')} value={field.value} onValueChange={(value) => { field.onChange(value); form.setValue('version_id', ''); }}
      options={[{ value: '', label: t('connector.choose') }, ...(prompts.data ?? []).map((prompt) => ({ value: prompt.prompt_id, label: prompt.model_name }))]} error={fieldState.error ? t('connector.invalid') : undefined} />} />
    {promptId && revisions.data?.length === 0 && !revisions.isFetching ? <p role="status">{t('connector.noRevisions')}</p> : null}
    <Controller control={form.control} name="version_id" render={({ field, fieldState }) => <Select label={t('connector.selectedRevision')} value={field.value} onValueChange={field.onChange} disabled={!promptId || revisions.isPending || revisions.isError}
      options={[{ value: '', label: t('connector.choose') }, ...(revisions.data ?? []).map((revision) => ({ value: revision.version_id, label: t('connector.revision', { number: revision.revision_number }) }))]} error={fieldState.error ? t('connector.invalid') : undefined} />} />
    <ConnectorError error={prompts.error ?? revisions.error} />
    <Button type="submit" disabled={!canOpen}>{t('connector.openWorkspace')}</Button>
  </form>;
}

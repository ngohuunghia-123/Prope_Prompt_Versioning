import { Controller } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import type { RevisionRead } from '@/features/prompt-lifecycle/types';
import type { Pending } from '@/features/connectors/contracts';
import { useCaptureForm } from '@/features/connectors/useCaptureForm';
import { ConnectorError } from '@/features/connectors/ConnectorError';

export function DestinationForm({ proposal, promptId, base }: { proposal: Pending; promptId: string; base?: RevisionRead }) {
  const { t } = useTranslation(); const { form, providers, models, preview, previewCurrent, convert, save } = useCaptureForm(proposal, promptId, base);
  return <form className="space-y-4" onSubmit={form.handleSubmit((values) => convert.mutate(values))}>
    <Input label={t('connector.namespace')} readOnly {...form.register('namespace')} />
    {!promptId ? <><Input label={t('connector.name')} {...form.register('name')} error={form.formState.errors.name ? t('connector.invalid') : undefined} />
      <Input label={t('connector.promptTitle')} {...form.register('title')} error={form.formState.errors.title ? t('connector.invalid') : undefined} /></> : null}
    {providers.isPending ? <p role="status">{t('common.loading')}</p> : <Controller control={form.control} name="provider_config_id" render={({ field, fieldState }) => <Select label={t('connector.provider')} value={field.value} onValueChange={(value) => { field.onChange(value); form.setValue('upstream_model', ''); }} disabled={Boolean(base)}
      options={[{ value: '', label: t('connector.choose') }, ...(providers.data ?? []).map((provider) => ({ value: provider.provider_config_id, label: provider.display_name }))]} error={fieldState.error ? t('connector.invalid') : undefined} />} />}
    {providers.data?.length === 0 ? <p>{t('connector.needProvider')}</p> : null}
    {!base && form.getValues('provider_config_id') && models.isPending ? <p role="status">{t('common.loading')}</p> : null}
    {!base && models.data?.filter((model) => model.available).length === 0 ? <p>{t('connector.noModels')}</p> : null}
    {base ? <Input label={t('connector.model')} readOnly {...form.register('upstream_model')} /> : <Controller control={form.control} name="upstream_model" render={({ field, fieldState }) => <Select label={t('connector.model')} value={field.value} onValueChange={field.onChange} disabled={models.isPending || models.isError}
      searchable options={[{ value: '', label: t('connector.choose') }, ...(models.data ?? []).filter((model) => model.available).map((model) => ({ value: model.model_id, label: model.model_id }))]} error={fieldState.error ? t('connector.invalid') : undefined} />} />}
    <Input label={t('connector.summary')} {...form.register('change_summary')} error={form.formState.errors.change_summary ? t('connector.invalid') : undefined} />
    <p className="text-caption text-muted">{t(proposal.input.kind !== 'evaluation' && proposal.input.format === 'xml' ? 'connector.canonicalHint' : 'connector.conversionCost')}</p>
    <ConnectorError error={providers.error ?? models.error ?? convert.error ?? save.error} />
    <Button type="submit" loading={convert.isPending} disabled={save.isPending}>{t(proposal.input.kind !== 'evaluation' && proposal.input.format === 'xml' ? 'connector.previewXml' : 'connector.preview')}</Button>
    {preview ? <section className="space-y-3" aria-label={t('connector.diff')}>
      <h3 className="font-display text-heading-3">{t('connector.diff')}</h3>
      <PromptBlockAccordion beforeBody={`<>\n${preview.base_body || preview.original}\n</>`} body={`<>\n${preview.body}\n</>`} sideBySide defaultExpanded />
      <p className="text-caption text-muted">{t('connector.confirmExact')}</p>
      <Button type="button" loading={save.isPending} disabled={!previewCurrent || convert.isPending} onClick={() => save.mutate()}>{t('connector.save')}</Button>
    </section> : null}
  </form>;
}

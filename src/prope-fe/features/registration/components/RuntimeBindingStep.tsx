import { Controller, type UseFormReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import type { RegistrationFormValues, RegistrationMetadata } from '@/features/registration/types';

export interface RuntimeBindingStepProps { form: UseFormReturn<RegistrationFormValues>; metadata: RegistrationMetadata; onProviderChange: (providerName: string) => void; }

export function RuntimeBindingStep({ form, metadata, onProviderChange }: RuntimeBindingStepProps) {
  const { t } = useTranslation();
  const provider = metadata.providers.find((item) => item.name === form.watch('providerName'));
  const errorText = (key: string | undefined) => key ? t(`registration.validation.${key}`) : undefined;
  return (
    <section>
      <h2 className="text-heading-2 font-semibold text-ink">{t('registration.binding.title')}</h2>
      <p className="mt-2 text-body text-muted">{t('registration.binding.description')}</p>
      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <Controller control={form.control} name="providerName" render={({ field }) => <Select label={t('registration.fields.provider')} value={field.value} error={errorText(form.formState.errors.providerName?.message)} onValueChange={(value) => { field.onChange(value); onProviderChange(value); }} options={metadata.providers.map((item) => ({ value: item.name, label: item.name }))} />} />
        <Controller control={form.control} name="upstreamModel" render={({ field }) => <Select label={t('registration.fields.upstreamModel')} value={field.value} error={errorText(form.formState.errors.upstreamModel?.message)} onValueChange={field.onChange} options={(provider?.models ?? []).map((model) => ({ value: model, label: model }))} />} />
        <Input type="number" min="0" max="2" step="0.1" label={t('registration.fields.temperature')} error={errorText(form.formState.errors.temperature?.message)} {...form.register('temperature', { valueAsNumber: true })} />
        <Input type="number" min="1" step="1" label={t('registration.fields.maxTokens')} error={errorText(form.formState.errors.maxTokens?.message)} {...form.register('maxTokens', { valueAsNumber: true })} />
        <Textarea className="sm:col-span-2" label={t('registration.fields.fallbackAnswer')} hint={t('registration.fields.fallbackHint')} error={errorText(form.formState.errors.fallbackAnswer?.message)} {...form.register('fallbackAnswer')} />
      </div>
    </section>
  );
}

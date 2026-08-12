import type { UseFormReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import type { RegistrationFormValues } from '@/features/registration/types';

export interface PromptRecordStepProps { form: UseFormReturn<RegistrationFormValues>; }

export function PromptRecordStep({ form }: PromptRecordStepProps) {
  const { t } = useTranslation();
  const errorText = (key: string | undefined) => key ? t(`registration.validation.${key}`) : undefined;
  return (
    <section>
      <h2 className="text-heading-2 font-semibold text-ink">{t('registration.record.title')}</h2>
      <p className="mt-2 text-body text-muted">{t('registration.record.description')}</p>
      <div className="mt-6 space-y-5">
        <Input label={t('registration.fields.title')} placeholder={t('registration.fields.titlePlaceholder')} error={errorText(form.formState.errors.title?.message)} {...form.register('title')} />
        <Input label={t('registration.fields.modelName')} placeholder={t('registration.fields.modelNamePlaceholder')} hint={t('registration.fields.modelNameHint')} error={errorText(form.formState.errors.modelName?.message)} {...form.register('modelName')} />
        <Input label={t('registration.fields.purpose')} placeholder={t('registration.fields.purposePlaceholder')} error={errorText(form.formState.errors.purpose?.message)} {...form.register('purpose')} />
        <Textarea label={t('registration.fields.content')} placeholder={t('registration.fields.contentPlaceholder')} hint={t('registration.fields.contentHint')} error={errorText(form.formState.errors.content?.message)} {...form.register('content')} />
        <Input label={t('registration.fields.tags')} placeholder={t('registration.fields.tagsPlaceholder')} hint={t('registration.fields.tagsHint')} {...form.register('tags')} />
      </div>
    </section>
  );
}

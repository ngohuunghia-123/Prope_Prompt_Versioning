import { zodResolver } from '@hookform/resolvers/zod';
import { Plus } from '@phosphor-icons/react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Select } from '@/components/ui/Select';
import { testInputFormSchema, type TestInputFormValues } from '@/features/evaluation/types';

interface TestInputFormProps { saving: boolean; onSubmit: (values: TestInputFormValues) => Promise<boolean>; }

export function TestInputForm({ saving, onSubmit }: TestInputFormProps) {
  const { t } = useTranslation();
  const { control, register, handleSubmit, formState: { errors }, reset } = useForm<TestInputFormValues>({
    resolver: zodResolver(testInputFormSchema),
    defaultValues: { name: '', content: '', assertionType: 'contains', expected: '' },
  });
  const submit = async (values: TestInputFormValues) => {
    if (await onSubmit(values)) reset();
  };
  return (
    <form onSubmit={(event) => void handleSubmit(submit)(event)} className="space-y-4 rounded-modal border border-border bg-canvas p-4 sm:p-5">
      <div><h3 className="text-heading-3 font-semibold text-ink">{t('evaluation.inputs.addTitle')}</h3><p className="mt-1 text-caption text-muted">{t('evaluation.inputs.addDescription')}</p></div>
      <Input label={t('evaluation.inputs.name')} placeholder={t('evaluation.inputs.namePlaceholder')} error={errors.name ? t('evaluation.validation.name') : undefined} {...register('name')} />
      <Textarea className="min-h-24" label={t('evaluation.inputs.content')} placeholder={t('evaluation.inputs.contentPlaceholder')} error={errors.content ? t('evaluation.validation.content') : undefined} {...register('content')} />
      <Controller name="assertionType" control={control} render={({ field }) => <Select label={t('evaluation.inputs.assertionType')} name={field.name} value={field.value} onValueChange={field.onChange} options={['contains', 'regex', 'json'].map((value) => ({ value, label: t(`evaluation.inputs.assertions.${value}`) }))} />} />
      <Input label={t('evaluation.inputs.expected')} error={errors.expected ? t('evaluation.validation.expected') : undefined} {...register('expected')} />
      <Button type="submit" intent="neutral" loading={saving} leadingIcon={<Plus aria-hidden className="size-4" />}>{t('evaluation.actions.addInput')}</Button>
    </form>
  );
}

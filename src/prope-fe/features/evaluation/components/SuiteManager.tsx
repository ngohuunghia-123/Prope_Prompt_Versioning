import { zodResolver } from '@hookform/resolvers/zod';
import { Plus } from '@phosphor-icons/react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { evaluationSuiteFormSchema, type EvaluationSuiteFormValues } from '@/features/evaluation/types';

interface SuiteManagerProps { saving: boolean; error: boolean; onCreate: (values: EvaluationSuiteFormValues) => Promise<boolean>; }

export function SuiteManager({ saving, error, onCreate }: SuiteManagerProps) {
  const { t } = useTranslation();
  const { control, register, handleSubmit, reset, formState: { errors } } = useForm<EvaluationSuiteFormValues>({ resolver: zodResolver(evaluationSuiteFormSchema), defaultValues: { name: '', outputModality: 'text' } });
  const submit = async (values: EvaluationSuiteFormValues) => { if (await onCreate(values)) reset(); };
  return <form onSubmit={(event) => void handleSubmit(submit)(event)} className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><p className="text-overline font-semibold text-muted">{t('evaluation.suiteManager.eyebrow')}</p><h2 className="mt-2 text-heading-2 font-semibold">{t('evaluation.suiteManager.title')}</h2><p className="mt-2 text-body text-muted">{t('evaluation.suiteManager.description')}</p><div className="mt-5 grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(14rem,0.7fr)_auto] sm:items-end"><Input label={t('evaluation.suiteManager.name')} error={errors.name ? t('evaluation.suiteManager.validation') : undefined} {...register('name')} /><Controller name="outputModality" control={control} render={({ field }) => <Select label={t('evaluation.suiteManager.modality')} name={field.name} value={field.value} onValueChange={field.onChange} options={['text', 'structured'].map((value) => ({ value, label: t(`evaluation.suites.modalities.${value}`) }))} />} /><Button type="submit" intent="neutral" loading={saving} leadingIcon={<Plus aria-hidden className="size-4" />}>{t('evaluation.suiteManager.create')}</Button></div>{error ? <p className="mt-3 text-caption font-semibold text-danger-text">{t('evaluation.suiteManager.error')}</p> : null}</form>;
}

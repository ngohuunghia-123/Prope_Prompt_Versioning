import { zodResolver } from '@hookform/resolvers/zod';
import { Controller, useForm } from 'react-hook-form';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { callLabelSchema, type CallLabel, type LabelingRecord } from '@/features/labeling/types';

const categories = ['incorrect', 'unsafe', 'incomplete', 'tone', 'format'] as const;
export function LabelForm({ record, saving, onSave }: { record: LabelingRecord; saving: boolean; onSave: (label: CallLabel) => void }) {
  const { t } = useTranslation();
  const form = useForm<CallLabel>({ resolver: zodResolver(callLabelSchema), defaultValues: record.label ?? { verdict: 'review', categories: [], correction: '', note: '' } });
  useEffect(() => form.reset(record.label ?? { verdict: 'review', categories: [], correction: '', note: '' }), [form, record]);
  return <form className="grid gap-4" onSubmit={(event) => void form.handleSubmit(onSave)(event)}>
    <Controller name="verdict" control={form.control} render={({ field }) => <Select label={t('labeling.form.verdict')} options={['good', 'issue', 'review'].map((value) => ({ value, label: t(`labeling.verdict.${value}`) }))} value={field.value} onValueChange={field.onChange} />} />
    <fieldset className="grid gap-2"><legend className="mb-1 text-body font-medium text-ink">{t('labeling.form.categories')}</legend>{categories.map((category) => <Controller key={category} name="categories" control={form.control} render={({ field }) => <Checkbox label={t(`labeling.category.${category}`)} checked={field.value.includes(category)} onChange={(event) => field.onChange(event.currentTarget.checked ? [...field.value, category] : field.value.filter((value) => value !== category))} />} />)}</fieldset>
    <Textarea label={t('labeling.form.correction')} {...form.register('correction')} />
    <Textarea label={t('labeling.form.note')} {...form.register('note')} />
    <Button type="submit" loading={saving}>{t('labeling.form.save')}</Button>
  </form>;
}

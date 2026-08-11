import { zodResolver } from '@hookform/resolvers/zod';
import { Buildings, LockKey, UsersThree } from '@phosphor-icons/react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Radio } from '@/components/ui/Radio';
import { accessFormSchema, type AccessFormValues, type AccessRecord } from '@/features/access-management/types';

interface AccessLevelFormProps {
  record: AccessRecord;
  saving: boolean;
  onSave: (values: AccessFormValues) => void;
}

const levels = [
  { value: 'private', Icon: LockKey },
  { value: 'team', Icon: UsersThree },
  { value: 'organization', Icon: Buildings },
] as const;

export function AccessLevelForm({ record, saving, onSave }: AccessLevelFormProps) {
  const { t } = useTranslation();
  const { register, handleSubmit, formState: { isDirty } } = useForm<AccessFormValues>({
    resolver: zodResolver(accessFormSchema),
    defaultValues: { access: record.access },
  });
  return (
    <form onSubmit={handleSubmit(onSave)} className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7">
      <p className="text-overline font-semibold text-muted">{t('accessManagement.access.eyebrow')}</p>
      <h2 className="mt-2 text-heading-2 font-semibold">{t('accessManagement.access.title')}</h2>
      <p className="mt-2 max-w-copy text-body text-muted">{t('accessManagement.access.description')}</p>
      <fieldset className="mt-6 grid gap-3 lg:grid-cols-3">
        <legend className="sr-only">{t('accessManagement.access.legend')}</legend>
        {levels.map(({ value, Icon }) => (
          <div key={value} className="rounded-modal border border-border bg-canvas p-4 has-[:checked]:border-secondary has-[:checked]:bg-accent-soft">
            <Icon aria-hidden className="size-6 text-secondary" />
            <Radio {...register('access')} value={value} label={t(`accessManagement.access.levels.${value}.title`)} className="mt-3 font-semibold" />
            <p className="mt-2 pl-7 text-body text-muted">{t(`accessManagement.access.levels.${value}.body`)}</p>
          </div>
        ))}
      </fieldset>
      <div className="mt-6 flex justify-end"><Button type="submit" loading={saving} disabled={!isDirty}>{t('accessManagement.actions.save')}</Button></div>
    </form>
  );
}

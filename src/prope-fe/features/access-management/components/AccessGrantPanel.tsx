import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, Trash } from '@phosphor-icons/react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { grantFormSchema, type AccessRecord, type GrantFormValues } from '@/features/access-management/types';

interface AccessGrantPanelProps {
  record: AccessRecord;
  saving: boolean;
  onGrant: (values: GrantFormValues) => void;
  onRevoke: (grantId: string) => void;
}

export function AccessGrantPanel({ record, saving, onGrant, onRevoke }: AccessGrantPanelProps) {
  const { t } = useTranslation();
  const { control, handleSubmit, reset, formState: { errors } } = useForm<GrantFormValues>({ resolver: zodResolver(grantFormSchema), defaultValues: { userId: '', level: 'viewer' } });
  const candidates = record.availableOwners.filter((owner) => owner.id !== record.ownerId);
  const submit = (values: GrantFormValues) => { onGrant(values); reset({ userId: '', level: 'viewer' }); };
  return (
    <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7" aria-labelledby="access-grants-title">
      <p className="text-overline font-semibold text-muted">{t('accessManagement.grants.eyebrow')}</p>
      <h2 id="access-grants-title" className="mt-2 text-heading-2 font-semibold">{t('accessManagement.grants.title')}</h2>
      <p className="mt-2 text-body text-muted">{t('accessManagement.grants.description')}</p>
      <form className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end" onSubmit={handleSubmit(submit)}>
        <Controller name="userId" control={control} render={({ field }) => <Select label={t('accessManagement.grants.person')} error={errors.userId ? t('accessManagement.validation.grantee') : undefined} name={field.name} value={field.value} onValueChange={field.onChange} options={[{ value: '', label: t('accessManagement.grants.choosePerson') }, ...candidates.map((person) => ({ value: person.id, label: person.name }))]} />} />
        <Controller name="level" control={control} render={({ field }) => <Select label={t('accessManagement.grants.level')} name={field.name} value={field.value} onValueChange={field.onChange} options={['viewer', 'editor'].map((level) => ({ value: level, label: t(`accessManagement.grants.levels.${level}`) }))} />} />
        <Button type="submit" loading={saving} leadingIcon={<Plus aria-hidden className="size-4" />}>{t('accessManagement.actions.grant')}</Button>
      </form>
      <div className="mt-5 space-y-2">
        {record.grants.length === 0 ? <p className="rounded-modal bg-subtle p-4 text-body text-muted">{t('accessManagement.grants.empty')}</p> : record.grants.map((grant) => (
          <div key={grant.id} className="flex items-center justify-between gap-3 rounded-modal border border-border p-3">
            <div><p className="text-body font-semibold">{grant.userName}</p><p className="text-caption text-muted">{t(`accessManagement.grants.levels.${grant.level}`)}</p></div>
            <Button type="button" intent="danger" aria-label={t('accessManagement.actions.revokeNamed', { name: grant.userName })} onClick={() => onRevoke(grant.id)}><Trash aria-hidden className="size-4" /></Button>
          </div>
        ))}
      </div>
    </section>
  );
}

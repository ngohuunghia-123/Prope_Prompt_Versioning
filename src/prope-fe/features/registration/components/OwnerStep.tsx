import { LockKey } from '@phosphor-icons/react';
import { Controller, type UseFormReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Radio } from '@/components/ui/Radio';
import { Select } from '@/components/ui/Select';
import type { RegistrationFormValues, RegistrationMetadata } from '@/features/registration/types';

export interface OwnerStepProps { form: UseFormReturn<RegistrationFormValues>; metadata: RegistrationMetadata; onOwnerChange: (ownerId: string) => void; }

export function OwnerStep({ form, metadata, onOwnerChange }: OwnerStepProps) {
  const { t } = useTranslation();
  const accessOptions = ['private', 'team', 'organization'] as const;
  return (
    <section><h2 className="text-heading-2 font-semibold text-ink">{t('registration.owner.title')}</h2><p className="mt-2 text-body text-muted">{t('registration.owner.description')}</p>
      <div className="mt-6 space-y-6"><Controller control={form.control} name="ownerId" render={({ field }) => <Select label={t('registration.owner.label')} value={field.value} onValueChange={(value) => { field.onChange(value); onOwnerChange(value); }} options={metadata.owners.map((owner) => ({ value: owner.id, label: `${owner.name} · ${t(`registration.owner.roles.${owner.role}`)}` }))} />} />
        <fieldset><legend className="text-body font-medium text-ink">{t('registration.access.label')}</legend><div className="mt-3 grid gap-3 sm:grid-cols-3">{accessOptions.map((access) => <div key={access} className="rounded-lg border border-border bg-surface p-3 has-focus-visible:outline-2 has-focus-visible:outline-focus"><Radio value={access} checked={form.watch('access') === access} label={t(`registration.access.${access}`)} {...form.register('access')} /></div>)}</div></fieldset>
        <div className="flex gap-3 rounded-modal border border-border-success bg-success p-4"><LockKey aria-hidden className="size-5 shrink-0 text-success-text" /><div><p className="text-body font-semibold text-ink">{t('registration.owner.privateTitle')}</p><p className="mt-1 text-caption text-muted">{t('registration.owner.privateBody')}</p></div></div>
      </div>
    </section>
  );
}

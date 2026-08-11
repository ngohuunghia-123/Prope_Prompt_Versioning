import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight, UserCircle } from '@phosphor-icons/react';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { transferFormSchema, type AccessRecord, type TransferFormValues } from '@/features/access-management/types';

interface OwnershipPanelProps { record: AccessRecord; transferring: boolean; onTransfer: (values: TransferFormValues) => void; }

export function OwnershipPanel({ record, transferring, onTransfer }: OwnershipPanelProps) {
  const { t } = useTranslation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { control, getValues, handleSubmit, watch, formState: { errors } } = useForm<TransferFormValues>({
    resolver: zodResolver(transferFormSchema),
    defaultValues: { newOwnerId: '' },
  });
  const selectedOwnerId = watch('newOwnerId');
  const nextOwner = record.availableOwners.find((owner) => owner.id === selectedOwnerId);
  const confirm = () => { onTransfer(getValues()); setConfirmOpen(false); };
  return (
    <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7" aria-labelledby="ownership-title">
      <p className="text-overline font-semibold text-muted">{t('accessManagement.ownership.eyebrow')}</p>
      <h2 id="ownership-title" className="mt-2 text-heading-2 font-semibold">{t('accessManagement.ownership.title')}</h2>
      <div className="mt-5 flex items-center gap-3 rounded-modal bg-subtle p-4"><UserCircle aria-hidden weight="duotone" className="size-10 text-secondary" /><div><p className="text-caption text-muted">{t('accessManagement.ownership.current')}</p><p className="text-body-large font-semibold">{record.ownerName}</p></div></div>
      <div className="mt-5">
        <Controller name="newOwnerId" control={control} render={({ field }) => <Select
          label={t('accessManagement.ownership.newOwner')}
          error={errors.newOwnerId ? t('accessManagement.validation.newOwner') : undefined}
          name={field.name}
          value={field.value}
          onValueChange={field.onChange}
          options={[{ value: '', label: t('accessManagement.ownership.chooseOwner') }, ...record.availableOwners.filter((owner) => owner.id !== record.ownerId).map((owner) => ({ value: owner.id, label: `${owner.name} — ${t(`registration.owner.roles.${owner.role}`)}` }))]}
        />} />
      </div>
      <p className="mt-3 text-caption text-muted">{t('accessManagement.ownership.warning')}</p>
      <div className="mt-5 flex justify-end"><Button type="button" intent="neutral" trailingIcon={<ArrowRight aria-hidden className="size-4" />} loading={transferring} onClick={() => void handleSubmit(() => setConfirmOpen(true))()}>{t('accessManagement.actions.transfer')}</Button></div>
      <Modal open={confirmOpen} title={t('accessManagement.transfer.title')} description={t('accessManagement.transfer.description', { name: nextOwner?.name ?? t('accessManagement.transfer.fallbackOwner') })} confirmLabel={t('accessManagement.actions.confirmTransfer')} onClose={() => setConfirmOpen(false)} onConfirm={confirm} />
    </section>
  );
}

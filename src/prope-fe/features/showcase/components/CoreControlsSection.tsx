import { ArrowRight, Plus } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Tag } from '@/components/Tag';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Input } from '@/components/ui/Input';
import { Radio } from '@/components/ui/Radio';
import { Select } from '@/components/ui/Select';
import { ShowcaseSection } from '@/features/showcase/components/ShowcaseSection';

export function CoreControlsSection() {
  const { t } = useTranslation();
  const [remember, setRemember] = useState(true);
  const [environment, setEnvironment] = useState('production');
  const statusOptions = [
    { value: '', label: t('showcase.statusPlaceholder'), disabled: true },
    { value: 'draft', label: t('status.draft') },
    { value: 'review', label: t('status.inReview') },
  ];
  return (
    <ShowcaseSection id="controls" title={t('showcase.foundations')}>
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="rounded-modal bg-surface p-5 shadow-panel sm:p-6">
          <h3 className="mb-4 text-heading-3 font-medium">{t('showcase.buttons')}</h3>
          <div className="flex flex-wrap items-center gap-3">
            <Button leadingIcon={<Plus aria-hidden className="size-4" />}>{t('showcase.submitted')}</Button>
            <Button intent="secondary" trailingIcon={<ArrowRight aria-hidden className="size-4" />}>{t('showcase.secondary')}</Button>
            <Button intent="neutral">{t('showcase.neutral')}</Button>
            <Button intent="success">{t('showcase.success')}</Button>
            <Button intent="warning">{t('showcase.warning')}</Button>
            <Button intent="info">{t('showcase.info')}</Button>
            <Button intent="danger">{t('showcase.danger')}</Button>
            <Button loading>{t('common.loading')}</Button>
          </div>
        </div>
        <div className="rounded-modal bg-surface p-5 shadow-panel sm:p-6">
          <h3 className="mb-4 text-heading-3 font-medium">{t('showcase.tags')}</h3>
          <div className="flex flex-wrap gap-3">
            <Tag>{t('showcase.tagOwnership')}</Tag><Tag state="neutral">{t('showcase.tagReview')}</Tag>
            <Tag state="warning">{t('showcase.tagRelease')}</Tag><Tag state="success">{t('status.approved')}</Tag><Tag state="danger">{t('status.retired')}</Tag>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <StatusBadge>{t('showcase.activeBadge')}</StatusBadge><StatusBadge tone="pending">{t('showcase.pendingBadge')}</StatusBadge>
            <StatusBadge tone="error">{t('showcase.errorBadge')}</StatusBadge><StatusBadge tone="disabled">{t('showcase.disabledBadge')}</StatusBadge>
          </div>
        </div>
        <div className="rounded-modal bg-surface p-5 shadow-panel sm:p-6">
          <h3 className="mb-4 text-heading-3 font-medium">{t('showcase.fields')}</h3>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Input name="prompt" label={t('showcase.inputLabel')} placeholder={t('showcase.promptPlaceholder')} hint={t('showcase.inputHint')} />
            <Input name="prompt-filled" label={t('showcase.filledFieldLabel')} defaultValue={t('showcase.filledFieldValue')} />
            <Input name="prompt-error" label={t('showcase.errorFieldLabel')} defaultValue={t('showcase.invalidFieldValue')} error={t('showcase.inputError')} />
            <Input name="prompt-disabled" label={t('showcase.disabledFieldLabel')} value={t('showcase.disabledFieldValue')} disabled readOnly />
            <Select name="status" label={t('showcase.selectLabel')} defaultValue="" options={statusOptions} />
            <Select name="status-selected" label={t('showcase.selectedSelectLabel')} defaultValue="draft" options={statusOptions} />
            <Select name="status-error" label={t('showcase.errorSelectLabel')} defaultValue="" error={t('showcase.selectError')} options={statusOptions} />
            <Select name="status-disabled" label={t('showcase.disabledSelectLabel')} defaultValue="draft" disabled options={statusOptions} />
          </div>
          <div className="mt-5 flex flex-wrap gap-5">
            <Checkbox label={t('showcase.remember')} checked={remember} onChange={(event) => setRemember(event.target.checked)} />
            <Checkbox label={t('showcase.disabledCheckbox')} checked disabled readOnly />
            <fieldset className="flex flex-wrap gap-4"><legend className="sr-only">{t('showcase.radioLegend')}</legend><Radio name="environment" label={t('showcase.production')} checked={environment === 'production'} onChange={() => setEnvironment('production')} /><Radio name="environment" label={t('showcase.staging')} checked={environment === 'staging'} onChange={() => setEnvironment('staging')} /></fieldset>
            <Radio name="disabled-environment" label={t('showcase.disabledRadio')} disabled />
          </div>
        </div>
        <Card title={t('showcase.cardTitle')}>{t('showcase.cardBody')}</Card>
      </div>
    </ShowcaseSection>
  );
}

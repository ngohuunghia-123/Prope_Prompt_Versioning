import { useTranslation } from 'react-i18next';
import { Button, Checkbox, Input, Radio, Select } from '@/components/ui';
import { ComponentShowcase } from '@/features/component-lab/components/ComponentShowcase';

export function FormComponentsSection() {
  const { t } = useTranslation();
  const buttonIntents = ['primary', 'secondary', 'neutral', 'success', 'warning', 'info', 'danger', 'ghost'] as const;
  const selectOptions = [
    { value: 'draft', label: t('status.draft') },
    { value: 'review', label: t('status.inReview') },
    { value: 'approved', label: t('status.approved') },
  ];
  return (
    <section className="space-y-5" aria-labelledby="component-lab-form-title">
      <h2 id="component-lab-form-title" className="text-heading-2 font-semibold text-ink">{t('componentLab.sections.form')}</h2>
      <div className="grid gap-5 lg:grid-cols-2">
        <ComponentShowcase name={t('componentLab.components.button')} source="components/ui/Button.tsx" kind="primitive">
          <div className="flex flex-wrap items-center gap-3">
            {buttonIntents.map((intent) => <Button key={intent} intent={intent}>{t(`componentLab.variants.button.${intent}`)}</Button>)}
            <Button disabled>{t('componentLab.variants.button.disabled')}</Button>
            <Button loading>{t('componentLab.variants.button.loading')}</Button>
            <Button size="icon" leadingIcon={<Plus aria-hidden className="size-4" />} aria-label={t('componentLab.variants.button.icon')} />
            <Button size="navigationIcon" leadingIcon={<Sparkle aria-hidden />} aria-label={t('componentLab.variants.button.navigationIcon')} />
          </div>
        </ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.input')} source="components/ui/Input.tsx" kind="primitive"><Input className="max-w-auth" label={t('auth.email')} placeholder={t('componentLab.samples.emailPlaceholder')} /></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.select')} source="components/ui/Select.tsx" kind="primitive"><Select className="max-w-auth" label={t('showcase.selectLabel')} options={selectOptions} defaultValue="draft" /></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.checkbox')} source="components/ui/Checkbox.tsx" kind="primitive"><Checkbox label={t('showcase.remember')} defaultChecked /></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.radio')} source="components/ui/Radio.tsx" kind="primitive"><Radio name="component-lab-environment" label={t('showcase.production')} defaultChecked /></ComponentShowcase>
      </div>
    </section>
  );
}
import { Plus, Sparkle } from '@phosphor-icons/react';

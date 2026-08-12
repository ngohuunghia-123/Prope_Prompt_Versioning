import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Logo, SegmentedControl, StatusBadge, Tabs, Tag } from '@/components';
import { ComponentShowcase } from '@/features/component-lab/components/ComponentShowcase';

export function DisplayComponentsSection() {
  const { t } = useTranslation();
  const [tab, setTab] = useState('overview');
  const [segment, setSegment] = useState('all');
  const tabs = [{ value: 'overview', label: t('showcase.tabOverview') }, { value: 'revisions', label: t('showcase.tabRevisions') }];
  const segments = [{ value: 'all', label: t('showcase.segmentAll') }, { value: 'active', label: t('showcase.segmentActive') }];
  const tagStates = ['default', 'neutral', 'warning', 'success', 'danger'] as const;
  return (
    <section className="space-y-5" aria-labelledby="component-lab-display-title">
      <h2 id="component-lab-display-title" className="text-heading-2 font-semibold text-ink">{t('componentLab.sections.display')}</h2>
      <div className="grid gap-5 lg:grid-cols-2">
        <ComponentShowcase name={t('componentLab.components.logo')} source="components/Logo.tsx" kind="composed"><Logo /></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.card')} source="components/Card.tsx" kind="composed"><Card className="w-full max-w-auth" title={t('showcase.cardTitle')}>{t('showcase.cardBody')}</Card></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.tag')} source="components/Tag.tsx" kind="composed">
          <div className="flex flex-wrap gap-3">
            {tagStates.map((state) => <Tag key={state} state={state}>{t(`componentLab.variants.tag.${state}`)}</Tag>)}
          </div>
        </ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.statusBadge')} source="components/StatusBadge.tsx" kind="composed"><StatusBadge tone="active">{t('showcase.activeBadge')}</StatusBadge></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.tabs')} source="components/Tabs.tsx" kind="composed"><Tabs className="w-full max-w-auth" label={t('showcase.tabsLabel')} items={tabs} value={tab} onValueChange={setTab} /></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.segmentedControl')} source="components/SegmentedControl.tsx" kind="composed"><SegmentedControl label={t('showcase.segmentsLabel')} name="component-lab-segment" options={segments} value={segment} onValueChange={setSegment} /></ComponentShowcase>
      </div>
    </section>
  );
}

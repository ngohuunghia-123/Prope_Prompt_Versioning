import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import { SegmentedControl } from '@/components/SegmentedControl';
import { Tabs } from '@/components/Tabs';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ShowcaseSection } from '@/features/showcase/components/ShowcaseSection';

export function ProductPatternsSection() {
  const { t } = useTranslation();
  const [tab, setTab] = useState('overview');
  const [segment, setSegment] = useState('all');
  const [modalOpen, setModalOpen] = useState(false);
  const [notificationVisible, setNotificationVisible] = useState(true);
  return (
    <ShowcaseSection id="patterns" title={t('showcase.patterns')}>
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="space-y-6 rounded-modal bg-surface p-5 shadow-panel sm:p-6">
          <h3 className="text-heading-3 font-medium">{t('showcase.navigation')}</h3>
          <Tabs label={t('showcase.tabsLabel')} value={tab} onValueChange={setTab} items={[{ value: 'overview', label: t('showcase.tabOverview') }, { value: 'revisions', label: t('showcase.tabRevisions') }, { value: 'evaluation', label: t('showcase.tabEvaluation') }]} />
          <SegmentedControl label={t('showcase.segmentsLabel')} name="prompt-filter" value={segment} onValueChange={setSegment} options={[{ value: 'all', label: t('showcase.segmentAll') }, { value: 'active', label: t('showcase.segmentActive') }, { value: 'pending', label: t('showcase.segmentPending') }, { value: 'disabled', label: t('showcase.segmentDisabled') }]} />
        </div>
        <div className="space-y-4 rounded-modal bg-surface p-5 shadow-panel sm:p-6">
          <h3 className="text-heading-3 font-medium">{t('showcase.feedback')}</h3>
          {notificationVisible ? <Notification title={t('showcase.notifyTitle')} onDismiss={() => setNotificationVisible(false)}>{t('showcase.notifyBody')}</Notification> : null}
          <Button onClick={() => setModalOpen(true)}>{t('showcase.openModal')}</Button>
          <Modal open={modalOpen} title={t('showcase.modalTitle')} description={t('showcase.modalBody')} confirmLabel={t('showcase.approve')} onClose={() => setModalOpen(false)} onConfirm={() => setModalOpen(false)} />
        </div>
      </div>
    </ShowcaseSection>
  );
}

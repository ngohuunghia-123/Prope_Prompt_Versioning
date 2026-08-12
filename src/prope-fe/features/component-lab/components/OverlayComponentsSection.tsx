import { SidebarSimple } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Drawer, Modal, Tooltip } from '@/components/ui';
import { Notification } from '@/components/Notification';
import { ComponentShowcase } from '@/features/component-lab/components/ComponentShowcase';

export function OverlayComponentsSection() {
  const { t } = useTranslation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  return (
    <section className="space-y-5" aria-labelledby="component-lab-overlay-title">
      <h2 id="component-lab-overlay-title" className="text-heading-2 font-semibold text-ink">{t('componentLab.sections.feedback')}</h2>
      <div className="grid gap-5 lg:grid-cols-2">
        <ComponentShowcase name={t('componentLab.components.tooltip')} source="components/ui/Tooltip.tsx" kind="primitive"><Tooltip label={t('componentLab.tooltipLabel')}><Button intent="neutral">{t('componentLab.tooltipTrigger')}</Button></Tooltip></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.modal')} source="components/ui/Modal.tsx" kind="primitive"><Button intent="secondary" onClick={() => setModalOpen(true)}>{t('showcase.openModal')}</Button></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.drawer')} source="components/ui/Drawer.tsx" kind="primitive"><Button intent="secondary" leadingIcon={<SidebarSimple aria-hidden className="size-4" />} onClick={() => setDrawerOpen(true)}>{t('componentLab.openDrawer')}</Button></ComponentShowcase>
        <ComponentShowcase name={t('componentLab.components.notification')} source="components/Notification.tsx" kind="composed"><Notification title={t('showcase.notifyTitle')}>{t('showcase.notifyBody')}</Notification></ComponentShowcase>
      </div>
      <Modal open={modalOpen} title={t('componentLab.modal.title')} description={t('componentLab.modal.description')} confirmLabel={t('common.confirm')} onClose={() => setModalOpen(false)} onConfirm={() => setModalOpen(false)} />
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <div className="space-y-3 px-2 pt-6"><h2 className="text-heading-2 font-semibold">{t('componentLab.drawerTitle')}</h2><p className="text-body text-muted">{t('componentLab.drawerBody')}</p></div>
      </Drawer>
    </section>
  );
}

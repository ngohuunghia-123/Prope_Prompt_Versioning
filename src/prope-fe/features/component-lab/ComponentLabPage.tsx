import { ArrowLeft, SidebarSimple } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Drawer } from '@/components/ui/Drawer';
import { Button } from '@/components/ui/Button';
import { Tooltip } from '@/components/ui/Tooltip';
import { Logo } from '@/components/Logo';
import { useTheme } from '@/lib/useTheme';
import { CoreControlsSection } from '@/features/showcase/components/CoreControlsSection';
import { ProductPatternsSection } from '@/features/showcase/components/ProductPatternsSection';

export function ComponentLabPage() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const nextTheme = theme === 'light' ? 'dark' : 'light';

  return (
    <main className="min-h-dvh bg-canvas text-ink">
      <header className="sticky top-0 z-30 border-b border-border bg-canvas/95 backdrop-blur-sm">
        <div className="mx-auto flex min-h-16 max-w-content items-center gap-3 px-4 py-3 sm:px-6">
          <Link to="/" className="inline-flex min-h-10 items-center gap-2 rounded-control px-3 text-body font-semibold text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus">
            <ArrowLeft aria-hidden className="size-4" />
            {t('componentLab.back')}
          </Link>
          <Logo variant="mark" className="shrink-0" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-heading-3 font-semibold sm:text-heading-2">{t('componentLab.title')}</h1>
          </div>
          <button type="button" onClick={() => void i18n.changeLanguage(i18n.language === 'vi' ? 'en' : 'vi')} aria-label={t('common.language')} className="grid size-10 place-items-center rounded-control text-caption font-semibold text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            {i18n.language === 'vi' ? t('common.englishShort') : t('common.vietnameseShort')}
          </button>
          <button type="button" onClick={() => setTheme(nextTheme)} className="min-h-10 rounded-control px-3 text-caption font-semibold text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            {t(nextTheme === 'dark' ? 'common.dark' : 'common.light')}
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-content space-y-12 px-4 py-10 sm:px-6 sm:py-14">
        <section className="max-w-copy space-y-3">
          <p className="text-body-large text-muted">{t('componentLab.description')}</p>
          <p className="text-caption text-muted">{t('componentLab.removalNote')}</p>
        </section>
        <CoreControlsSection />
        <ProductPatternsSection />
        <section className="space-y-5" aria-labelledby="component-lab-overlay-title">
          <div className="flex items-center gap-3"><span aria-hidden className="h-px w-8 bg-secondary" /><h2 id="component-lab-overlay-title" className="text-heading-2 font-semibold">{t('componentLab.overlays')}</h2></div>
          <div className="flex flex-wrap items-center gap-4 rounded-modal bg-surface p-5 shadow-panel sm:p-6">
            <Button intent="secondary" leadingIcon={<SidebarSimple aria-hidden className="size-4" />} onClick={() => setDrawerOpen(true)}>{t('componentLab.openDrawer')}</Button>
            <Tooltip label={t('componentLab.tooltipLabel')}>
              <Button intent="neutral">{t('componentLab.tooltipTrigger')}</Button>
            </Tooltip>
          </div>
        </section>
      </div>
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <div className="space-y-3 px-2 pt-6">
          <h2 className="text-heading-2 font-semibold">{t('componentLab.drawerTitle')}</h2>
          <p className="text-body text-muted">{t('componentLab.drawerBody')}</p>
        </div>
      </Drawer>
    </main>
  );
}

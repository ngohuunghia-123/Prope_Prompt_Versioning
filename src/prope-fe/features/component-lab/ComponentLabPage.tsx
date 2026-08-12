import { CaretRight, FolderOpen } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { DisplayComponentsSection } from '@/features/component-lab/components/DisplayComponentsSection';
import { FormComponentsSection } from '@/features/component-lab/components/FormComponentsSection';
import { OverlayComponentsSection } from '@/features/component-lab/components/OverlayComponentsSection';

export function ComponentLabPage() {
  const { t, i18n } = useTranslation();

  return (
    <main className="min-h-dvh bg-canvas text-ink">
      <header className="sticky top-0 z-30 border-b border-border bg-canvas/95 backdrop-blur-sm">
        <div className="mx-auto flex min-h-16 max-w-content items-center gap-3 px-4 py-3 sm:px-6">
          <nav aria-label={t('common.breadcrumb')} className="min-w-0 flex-1"><ol className="flex min-w-0 items-center gap-1 text-body"><li className="flex min-w-0 items-center gap-2"><FolderOpen aria-hidden className="size-4 shrink-0 text-secondary" /><Link to="/app/prompts" className="truncate text-muted hover:text-link focus-visible:outline-2 focus-visible:outline-focus">{t('navigation.workspace')}</Link></li><li className="flex min-w-0 items-center gap-1"><CaretRight aria-hidden className="size-4 shrink-0 text-muted" /><span aria-current="page" className="truncate font-medium text-ink">{t('componentLab.title')}</span></li></ol></nav>
          <button type="button" onClick={() => void i18n.changeLanguage(i18n.language === 'vi' ? 'en' : 'vi')} aria-label={t('common.language')} className="grid size-10 place-items-center rounded-control text-caption font-semibold text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            {i18n.language === 'vi' ? t('common.englishShort') : t('common.vietnameseShort')}
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-content space-y-12 px-4 py-10 sm:px-6 sm:py-14">
        <section className="max-w-copy space-y-3">
          <p className="text-body-large text-muted">{t('componentLab.description')}</p>
        </section>
        <FormComponentsSection />
        <OverlayComponentsSection />
        <DisplayComponentsSection />
      </div>
    </main>
  );
}

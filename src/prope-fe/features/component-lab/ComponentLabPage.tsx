import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { useTheme } from '@/lib/useTheme';
import { DisplayComponentsSection } from '@/features/component-lab/components/DisplayComponentsSection';
import { FormComponentsSection } from '@/features/component-lab/components/FormComponentsSection';
import { OverlayComponentsSection } from '@/features/component-lab/components/OverlayComponentsSection';

export function ComponentLabPage() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const nextTheme = theme === 'light' ? 'dark' : 'light';

  return (
    <main className="min-h-dvh bg-canvas text-ink">
      <header className="sticky top-0 z-30 border-b border-border bg-canvas/95 backdrop-blur-sm">
        <div className="mx-auto flex min-h-16 max-w-content items-center gap-3 px-4 py-3 sm:px-6">
          <Link to="/app/prompts" className="inline-flex min-h-10 items-center rounded-control px-3 text-body font-semibold text-muted hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus">{t('componentLab.back')}</Link>
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
        </section>
        <FormComponentsSection />
        <OverlayComponentsSection />
        <DisplayComponentsSection />
      </div>
    </main>
  );
}

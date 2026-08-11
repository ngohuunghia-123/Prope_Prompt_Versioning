import { SidebarSimple } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Logo } from '@/components/Logo';

export interface NavigationBrandHeaderProps { onCollapse: () => void; }

export function NavigationBrandHeader({ onCollapse }: NavigationBrandHeaderProps) {
  const { t } = useTranslation();
  return (
    <div className="flex min-w-0 items-center justify-between gap-3">
      <a href="/" aria-label={t('common.propeHome')} className="inline-flex min-w-0 items-center gap-1 text-secondary no-underline focus-visible:outline-2 focus-visible:outline-focus"><Logo className="min-w-0" /></a>
      <button type="button" onClick={onCollapse} aria-label={t('common.collapseNavigation')} aria-expanded title={t('common.collapseNavigation')} className="grid size-8 shrink-0 place-items-center rounded-navigation-control bg-transparent p-0 text-navigation-icon shadow-none transition-colors hover:bg-surface/55 hover:text-navigation-active focus-visible:outline-2 focus-visible:outline-focus">
        <SidebarSimple aria-hidden className="size-navigation-icon-large" />
      </button>
    </div>
  );
}

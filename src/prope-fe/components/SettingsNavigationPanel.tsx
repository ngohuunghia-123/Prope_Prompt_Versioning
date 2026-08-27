import { ArrowLeft } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { NavigationMenu, type NavigationItem } from '@/components/NavigationMenu';

export interface SettingsNavigationPanelProps {
  activeId: string;
  items: NavigationItem[];
}

export function SettingsNavigationPanel({ activeId, items }: SettingsNavigationPanelProps) {
  const { t } = useTranslation();
  return (
    <div data-navigation-panel="settings" className="flex h-full min-w-0 flex-col gap-3.5 overflow-hidden px-4 pt-3.5">
      <Link
        to="/app/prompts"
        className="flex min-h-8 shrink-0 items-center gap-2 rounded-navigation-control px-2 text-body text-link transition-colors hover:bg-surface/55 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
      >
        <ArrowLeft aria-hidden className="size-navigation-icon" />
        <span className="font-semibold">{t('navigation.advanced.home.settingsPanel')}</span>
      </Link>

      <section aria-label={t('navigation.advanced.home.settingsPanel')} className="min-h-0 flex-1 overflow-hidden pt-1">
        <div className="h-full overflow-y-auto overflow-x-hidden pb-3 pr-1 pt-1.5 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
          <NavigationMenu items={items} activeId={activeId} />
        </div>
      </section>
    </div>
  );
}

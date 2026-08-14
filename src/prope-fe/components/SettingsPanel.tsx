import { X } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { useState, type ReactNode } from 'react';
import { ApiKeysPanel } from './settings/ApiKeysPanel';
import { GeneralPanel } from './settings/GeneralPanel';
import { WorkspacePanel } from './settings/WorkspacePanel';
import { NotificationsPanel } from './settings/NotificationsPanel';
import { SETTING_ITEMS, type SettingsItem, type SettingsItemId } from '@/components/settingsItems';

export interface SettingsPanelProps {
  onClose: () => void;
}

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  const { t } = useTranslation();
  const [activeItem, setActiveItem] = useState<SettingsItemId | null>(null);

  const handleItemClick = (item: SettingsItem) => {
    setActiveItem(item.id);
  };

  const handleBack = () => {
    if (activeItem) {
      setActiveItem(null);
    } else {
      onClose();
    }
  };

  const renderContent = (): ReactNode => {
    if (!activeItem) return null;

    switch (activeItem) {
      case 'api-keys':
        return <ApiKeysPanel />;
      case 'general':
        return <GeneralPanel />;
      case 'workspace':
        return <WorkspacePanel />;
      case 'notifications':
        return <NotificationsPanel />;
      default:
        return null;
    }
  };

  const currentItem = SETTING_ITEMS.find((item) => item.id === activeItem);

  return (
    <section
      aria-label={t('navigation.advanced.home.settingsPanel')}
      className="flex h-full min-h-0 animate-navigation-panel flex-col overflow-hidden"
    >
      <div className="flex items-center gap-2 border-b border-border/60 pb-2.5">
        <button
          type="button"
          onClick={handleBack}
          aria-label={activeItem ? t('navigation.advanced.home.backToSettings') : t('navigation.advanced.home.backToHome')}
          className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-muted transition-colors duration-(--prope-motion-duration-fast) hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
        >
          {activeItem ? (
            <X aria-hidden className="size-5" />
          ) : currentItem ? (
            <currentItem.icon aria-hidden className="size-5" />
          ) : null}
        </button>
        <nav aria-label={t('common.breadcrumb')} className="flex min-w-0 items-center gap-1 text-body">
          <span className="text-muted">{t('navigation.advanced.home.settingsPanel')}</span>
          {activeItem && (
            <>
              <span aria-hidden className="text-muted">/</span>
              <span className="font-medium text-ink">{currentItem ? t(currentItem.labelKey) : ''}</span>
            </>
          )}
        </nav>
      </div>

      {activeItem ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-1 py-3 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
          {renderContent()}
        </div>
      ) : (
        <nav className="mt-3 flex-1 space-y-1 overflow-y-auto px-1 pr-1 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
          {SETTING_ITEMS.map(({ id, labelKey, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => handleItemClick({ id, labelKey, icon: Icon })}
              className="flex w-full min-w-0 items-center gap-2 rounded-navigation-control px-2 py-1.5 text-left text-body text-link transition-colors duration-(--prope-motion-duration-fast) hover:bg-surface/55 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
            >
              <span className="shrink-0 text-secondary">
                <Icon aria-hidden className="size-5" />
              </span>
              <span className="truncate">{t(labelKey)}</span>
            </button>
          ))}
        </nav>
      )}
    </section>
  );
}

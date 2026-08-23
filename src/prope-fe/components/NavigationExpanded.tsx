import type { ReactNode } from 'react';
import { NavigationBrandHeader } from '@/components/NavigationBrandHeader';
import type { NavigationItem } from '@/components/NavigationMenu';
import { PrimaryNavigationPanel } from '@/components/PrimaryNavigationPanel';
import { SettingsNavigationPanel } from '@/components/SettingsNavigationPanel';
import type { NavigationMode } from '@/components/navigationTypes';

export interface NavigationExpandedProps {
  activeId: string;
  items?: NavigationItem[];
  account?: ReactNode;
  mode: NavigationMode;
  onCollapse: () => void;
  onModeChange: (mode: NavigationMode) => void;
}

export function NavigationExpanded({ activeId, items, account, mode, onCollapse, onModeChange }: NavigationExpandedProps) {
  const isSettings = activeId.startsWith('settings/');
  return (
    <div className="flex h-full min-w-0 max-w-full flex-col overflow-hidden">
      <header className="shrink-0 px-4 pt-2.5">
        <NavigationBrandHeader onCollapse={onCollapse} />
      </header>
      <div className="min-h-0 flex-1 overflow-hidden">
        {isSettings
          ? <SettingsNavigationPanel activeId={activeId} items={items ?? []} />
          : <PrimaryNavigationPanel activeId={activeId} items={items} mode={mode} onModeChange={onModeChange} />}
      </div>
      {(isSettings || mode === 'home') && account ? <footer className="mx-4 shrink-0 border-t border-border/60 bg-navigation-surface pb-2.5 pt-2.5">{account}</footer> : null}
    </div>
  );
}

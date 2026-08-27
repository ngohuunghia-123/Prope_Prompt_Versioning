import type { NavigationItem } from '@/components/NavigationMenu';
import { PrimaryNavigationPanel } from '@/components/PrimaryNavigationPanel';
import { SettingsNavigationPanel } from '@/components/SettingsNavigationPanel';
import type { NavigationMode } from '@/components/navigationTypes';

export interface NavigationExpandedViewProps {
  activeId: string;
  items?: NavigationItem[];
  isSettings: boolean;
  mode: NavigationMode;
  onModeChange: (mode: NavigationMode) => void;
}

export function NavigationExpandedView({ activeId, items, isSettings, mode, onModeChange }: NavigationExpandedViewProps) {
  return isSettings
    ? <SettingsNavigationPanel activeId={activeId} items={items ?? []} />
    : <PrimaryNavigationPanel activeId={activeId} items={items} mode={mode} onModeChange={onModeChange} />;
}

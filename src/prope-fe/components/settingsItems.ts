import { Bell, Gear, Key, UsersThree } from '@phosphor-icons/react';

export type SettingsItemId = 'api-keys' | 'general' | 'workspace' | 'notifications';

export interface SettingsItem {
  id: SettingsItemId;
  labelKey: string;
  icon: typeof Gear;
}

export const SETTING_ITEMS: SettingsItem[] = [
  { id: 'api-keys', labelKey: 'navigation.advanced.home.settingsItems.apiKeys', icon: Key },
  { id: 'general', labelKey: 'navigation.advanced.home.settingsItems.general', icon: Gear },
  { id: 'workspace', labelKey: 'navigation.advanced.home.settingsItems.workspace', icon: UsersThree },
  { id: 'notifications', labelKey: 'navigation.advanced.home.settingsItems.notifications', icon: Bell },
];

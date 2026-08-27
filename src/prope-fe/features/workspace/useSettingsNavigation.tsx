import { IdentificationCard, Key, PlugsConnected, TreeStructure, UsersThree } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { NavigationItem } from '@/components/NavigationMenu';

export function useSettingsNavigation(): NavigationItem[] {
  const { t } = useTranslation();

  return [
    { id: 'settings/profile', label: t('account.profile.navigation'), href: '/app/settings/profile', icon: <IdentificationCard className="size-navigation-icon" /> },
    { id: 'settings/keys', label: t('lifecycle.navigation.keys'), href: '/app/settings/keys', icon: <Key className="size-navigation-icon" /> },
    { id: 'settings/providers', label: t('lifecycle.navigation.providers'), href: '/app/settings/providers', icon: <PlugsConnected className="size-navigation-icon" /> },
    { id: 'settings/router', label: t('lifecycle.navigation.router'), href: '/app/settings/router', icon: <TreeStructure className="size-navigation-icon" /> },
    { id: 'settings/workspace', label: t('lifecycle.navigation.workspace'), href: '/app/settings/workspace', icon: <UsersThree className="size-navigation-icon" /> },
  ];
}

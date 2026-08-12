import { ClockCounterClockwise, FolderOpen, PlugsConnected, Scroll } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { NavigationItem } from '@/components/NavigationMenu';

export function useLifecycleNavigation(): NavigationItem[] {
  const { t } = useTranslation();
  return [
    { id: 'vault/prompts', label: t('lifecycle.navigation.registry'), href: '/app/prompts', icon: <FolderOpen className="size-navigation-icon" /> },
    { id: 'vault/reviews', label: t('lifecycle.navigation.reviews'), href: '/app/reviews', icon: <ClockCounterClockwise className="size-navigation-icon" /> },
    { id: 'vault/providers', label: t('lifecycle.navigation.providers'), href: '/app/providers', icon: <PlugsConnected className="size-navigation-icon" /> },
    { id: 'vault/calls', label: t('lifecycle.navigation.calls'), href: '/app/calls', icon: <Scroll className="size-navigation-icon" /> },
  ];
}

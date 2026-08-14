import { ChartLineUp, Compass, Database, GearSix, Play, Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { NavigationItem } from '@/components/NavigationMenu';

export function useNavigationHomeData() {
  const { t } = useTranslation();
  const overviewItems: NavigationItem[] = [
    { id: 'dashboard', label: t('navigation.advanced.home.dashboard'), href: '/app/dashboard', icon: <Compass className="size-navigation-icon" /> },
    { id: 'vault', label: t('navigation.advanced.home.promptVault'), href: '/app/vault', icon: <Sparkle className="size-navigation-icon" /> },
    { id: 'playground', label: t('navigation.advanced.home.playground'), href: '/app/playground', icon: <Play className="size-navigation-icon" /> },
  ];
  const evaluationItems: NavigationItem[] = [
    { id: 'testing-dataset', label: t('navigation.advanced.home.testingDataset'), href: '/app/testing-dataset', icon: <Database className="size-navigation-icon" /> },
  ];
  return {
    groups: [
      { id: 'overview', label: t('navigation.advanced.home.overview'), compactLabel: t('navigation.advanced.home.overview'), icon: <Compass aria-hidden className="size-navigation-icon" />, items: overviewItems },
      { id: 'evaluation', label: t('navigation.advanced.home.evaluation'), compactLabel: t('navigation.advanced.home.evaluation'), icon: <ChartLineUp aria-hidden className="size-navigation-icon" />, items: evaluationItems },
    ],
    supportLinks: [
      { id: 'settings', label: t('navigation.advanced.home.settings'), href: '/app/settings', icon: <GearSix aria-hidden className="size-navigation-icon" /> },
    ],
  };
}

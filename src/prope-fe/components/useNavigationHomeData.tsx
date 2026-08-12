import { ChartLineUp, Chats, CheckSquare, FileText, Folder, GearSix, Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { NavigationItem } from '@/components/NavigationMenu';

export function useNavigationHomeData(items?: NavigationItem[]) {
  const { t } = useTranslation();
  const vaultItems: NavigationItem[] = items?.length ? items : [
    { id: 'vault/folder-1', label: t('navigation.advanced.home.productPrompts'), href: '/app/vault/folder-1', icon: <Folder className="size-navigation-icon" /> },
    { id: 'vault/folder-1/customer-support', label: t('navigation.advanced.home.customerSupport'), href: '/app/vault/folder-1/customer-support', icon: <FileText className="size-navigation-icon" />, child: true },
    { id: 'vault/folder-1/claim-screening', label: t('navigation.advanced.home.claimScreening'), href: '/app/vault/folder-1/claim-screening', icon: <FileText className="size-navigation-icon" />, child: true },
  ];
  const evaluationItems: NavigationItem[] = [
    { id: 'evaluation/datasets', label: t('navigation.advanced.home.evalDatasets'), href: '/app/evaluation/datasets', icon: <Folder className="size-navigation-icon" /> },
    { id: 'evaluation/review-queue', label: t('navigation.advanced.home.reviewQueue'), href: '/app/evaluation/review-queue', icon: <CheckSquare className="size-navigation-icon" /> },
    { id: 'evaluation/reports', label: t('navigation.advanced.home.reports'), href: '/app/evaluation/reports', icon: <ChartLineUp className="size-navigation-icon" /> },
  ];
  return {
    groups: [
      { id: 'vault', label: t('navigation.advanced.home.promptVault'), compactLabel: t('navigation.advanced.compact.vault'), icon: <Folder aria-hidden className="size-navigation-icon" />, items: vaultItems },
      { id: 'evaluation', label: t('navigation.advanced.home.evaluation'), compactLabel: t('navigation.advanced.compact.evaluation'), icon: <ChartLineUp aria-hidden className="size-navigation-icon" />, items: evaluationItems },
    ],
    supportLinks: [
      { id: 'whats-new', label: t('navigation.advanced.home.whats-new'), href: '/app/whats-new', icon: <Sparkle aria-hidden className="size-navigation-icon" /> },
      { id: 'contact', label: t('navigation.advanced.home.contact'), href: '/app/contact', icon: <Chats aria-hidden className="size-navigation-icon" /> },
      { id: 'settings', label: t('navigation.advanced.home.settings'), href: '/app/settings', icon: <GearSix aria-hidden className="size-navigation-icon" /> },
    ],
  };
}

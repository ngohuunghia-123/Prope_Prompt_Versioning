import { ChartLineUp, FolderOpen, GearSix } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { NavigationItem } from '@/components/NavigationMenu';
import { useLifecycleNavigation } from '@/features/prompt-lifecycle/useLifecycleNavigation';

/**
 * The sidebar's groups, built from the one list of real destinations.
 *
 * This used to hold its own hardcoded set — `/app/dashboard`, `/app/vault`,
 * `/app/playground`, `/app/testing-dataset` — and none of those were routes, so
 * every item in the sidebar fell through `PromptLifecycleRoutes`' catch-all and
 * landed on the prompt registry. The Providers page had a route and an entry in
 * `useLifecycleNavigation` the whole time, but that list was passed down as an
 * `items` prop that `NavigationHomePanel` never read, so there was no way to
 * reach the page except by typing the URL.
 *
 * Grouping is by id prefix rather than a second list, because the collapsed rail
 * decides which group is current by testing `activeId.startsWith(group.id)` —
 * two independent groupings would disagree the first time one of them changed.
 */
export function useNavigationHomeData() {
  const { t } = useTranslation();
  const items = useLifecycleNavigation();
  const inGroup = (prefix: string): NavigationItem[] => items.filter((item) => item.id.startsWith(`${prefix}/`));

  return {
    groups: [
      {
        id: 'registry',
        label: t('navigation.advanced.home.registry'),
        compactLabel: t('navigation.advanced.home.registry'),
        icon: <FolderOpen aria-hidden className="size-navigation-icon" />,
        items: inGroup('registry'),
      },
      {
        id: 'evaluation',
        label: t('navigation.advanced.home.evaluation'),
        compactLabel: t('navigation.advanced.home.evaluation'),
        icon: <ChartLineUp aria-hidden className="size-navigation-icon" />,
        items: inGroup('evaluation'),
      },
    ],
    supportLinks: [
      { id: 'settings', label: t('navigation.advanced.home.settings'), href: '/app/settings/profile', icon: <GearSix aria-hidden className="size-navigation-icon" /> },
    ],
  };
}

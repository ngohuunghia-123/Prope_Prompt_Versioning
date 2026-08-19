import { Database, FolderOpen, TerminalWindow } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { NavigationItem } from '@/components/NavigationMenu';

/**
 * Every place the workspace can actually navigate to.
 *
 * One list, and every `href` in it resolves to a route in
 * `PromptLifecycleRoutes`. That is not a given: the sidebar used to render a
 * separate hardcoded set — dashboard, vault, playground, testing-dataset — none
 * of which matched a route, so all four fell through the `*` case and bounced to
 * `/app/prompts`. Anything added here must have a route, or it becomes another
 * link that silently goes somewhere else.
 *
 * The id prefix is also the group it belongs to (`useNavigationHomeData` slices
 * on it), and the collapsed rail highlights a group by testing the active id
 * against that prefix — so an id and its group cannot be chosen independently.
 */
export function useLifecycleNavigation(): NavigationItem[] {
  const { t } = useTranslation();
  return [
    { id: 'registry/prompts', label: t('lifecycle.navigation.registry'), href: '/app/prompts', icon: <FolderOpen className="size-navigation-icon" /> },
    { id: 'registry/playground', label: t('lifecycle.navigation.playground'), href: '/app/playground', icon: <TerminalWindow className="size-navigation-icon" /> },
    { id: 'evaluation/datasets', label: t('lifecycle.navigation.datasets'), href: '/app/datasets', icon: <Database className="size-navigation-icon" /> },
  ];
}

/** The nav id for a URL's first segment. Drives which entry reads as current. */
export const NAVIGATION_ID_BY_SECTION: Record<string, string> = {
  prompts: 'registry/prompts',
  search: 'registry/prompts',
  playground: 'registry/playground',
  keys: 'settings',
  reviews: 'registry/prompts',
  releases: 'registry/prompts',
  datasets: 'evaluation/datasets',
  providers: 'settings',
  workspace: 'settings',
  // Not group members — these are the navigation footer's two entries, and the
  // ids match what `useNavigationHomeData` gives its support links so the
  // footer highlights while you are on them.
  settings: 'settings',
  account: 'account',
};

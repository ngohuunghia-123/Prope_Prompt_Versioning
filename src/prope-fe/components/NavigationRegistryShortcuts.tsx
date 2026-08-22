import { Folder, FolderOpen } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { NavigationMenu } from '@/components/NavigationMenu';
import { foldersOptions } from '@/features/prompt-lifecycle/queries';
import { useTranslation } from 'react-i18next';

interface NavigationRegistryShortcutsProps {
  activeId: string;
}

export function NavigationRegistryShortcuts({ activeId }: NavigationRegistryShortcutsProps) {
  const { t } = useTranslation();
  const folders = useQuery(foldersOptions);
  const allFolders = [...(folders.data ?? [])]
    .sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt))
  const items = allFolders.slice(0, 3).map((folder) => ({
    id: `registry/folder/${folder.id}`,
    label: folder.name,
    href: `/app/prompts/folder/${encodeURIComponent(folder.id)}`,
    icon: <Folder aria-hidden className="size-navigation-icon" />,
    child: true,
  }));
  if (allFolders.length > 3) items.push({ id: 'registry/folder/all', label: t('lifecycle.navigation.viewAllFolders'), href: '/app/prompts', icon: <FolderOpen aria-hidden className="size-navigation-icon" />, child: true });

  return items.length > 0 ? (
    <div className="relative ml-5 border-l border-border pl-2 before:absolute before:-left-px before:top-0 before:h-3 before:border-l before:border-border">
      <NavigationMenu items={items} activeId={activeId} />
    </div>
  ) : null;
}

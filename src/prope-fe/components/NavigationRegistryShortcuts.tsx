import { Folder } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { NavigationMenu } from '@/components/NavigationMenu';
import { foldersOptions } from '@/features/prompt-lifecycle/queries';

interface NavigationRegistryShortcutsProps {
  activeId: string;
}

export function NavigationRegistryShortcuts({ activeId }: NavigationRegistryShortcutsProps) {
  const folders = useQuery(foldersOptions);
  const items = (folders.data ?? []).map((folder) => ({
    id: `registry/folder/${folder.id}`,
    label: folder.name,
    href: `/app/prompts/folder/${encodeURIComponent(folder.id)}`,
    icon: <Folder aria-hidden className="size-navigation-icon" />,
    child: true,
  }));

  return items.length > 0 ? (
    <div className="relative ml-5 border-l border-border pl-2 before:absolute before:-left-px before:top-0 before:h-3 before:border-l before:border-border">
      <NavigationMenu items={items} activeId={activeId} />
    </div>
  ) : null;
}

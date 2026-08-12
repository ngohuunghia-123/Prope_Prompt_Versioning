import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { Tooltip } from '@/components/ui/Tooltip';

export interface NavigationItem { id: string; label: string; href: string; icon: ReactNode; child?: boolean; }
export interface NavigationMenuProps { items: NavigationItem[]; activeId: string; collapsed?: boolean; label?: string; onNavigate?: () => void; }

export function NavigationMenu({ items, activeId, collapsed = false, label, onNavigate }: NavigationMenuProps) {
  const { t } = useTranslation();
  return (
    <nav aria-label={label ?? t('navigation.advanced.workspaceLabel')} className="grid min-w-0 gap-2 overflow-hidden">
      {label ? <p className="m-0 text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{label}</p> : null}
      <ul className="grid gap-2">
        {items.map((item) => {
          const link = (
            <Link to={item.href} aria-current={activeId === item.id ? 'page' : undefined} onClick={onNavigate} className={cn('flex min-h-8 min-w-0 items-center gap-2 rounded-navigation-control px-2 text-body text-link transition-colors duration-(--prope-motion-duration-fast) hover:bg-surface/55 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus', activeId === item.id && 'bg-surface font-semibold text-navigation-active shadow-inset', item.child && 'pl-6', collapsed && 'justify-center px-0')}>
              <span aria-hidden className="grid size-navigation-icon shrink-0 place-items-center text-secondary">{item.icon}</span>
              {!collapsed ? <span className="truncate text-body">{item.label}</span> : <span className="sr-only">{item.label}</span>}
            </Link>
          );
          return <li key={item.id}>{collapsed ? <Tooltip label={item.label}>{link}</Tooltip> : link}</li>;
        })}
      </ul>
    </nav>
  );
}

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { Tooltip } from '@/components/ui/Tooltip';

export interface NavigationItem { id: string; label: string; href: string; icon: ReactNode; }
export interface NavigationMenuProps { items: NavigationItem[]; activeId: string; collapsed?: boolean; onNavigate?: () => void; }

export function NavigationMenu({ items, activeId, collapsed = false, onNavigate }: NavigationMenuProps) {
  return (
    <nav aria-label="Prope" className="min-h-0 flex-1 overflow-y-auto py-4">
      <ul className="space-y-1">
        {items.map((item) => {
          const link = (
            <Link to={item.href} aria-current={activeId === item.id ? 'page' : undefined} onClick={onNavigate} className={cn('flex min-h-11 items-center gap-3 rounded-lg px-3 text-body font-medium text-muted transition-colors hover:bg-surface/65 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus', activeId === item.id && 'bg-surface text-link shadow-inset', collapsed && 'justify-center px-0')}>
              <span aria-hidden className="grid size-6 shrink-0 place-items-center">{item.icon}</span>
              {!collapsed ? <span className="truncate">{item.label}</span> : <span className="sr-only">{item.label}</span>}
            </Link>
          );
          return <li key={item.id}>{collapsed ? <Tooltip label={item.label}>{link}</Tooltip> : link}</li>;
        })}
      </ul>
    </nav>
  );
}

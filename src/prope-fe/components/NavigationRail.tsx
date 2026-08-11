import { CaretDoubleLeft, CaretDoubleRight } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import { Logo } from '@/components/Logo';
import { NavigationMenu, type NavigationItem } from '@/components/NavigationMenu';
import { Tooltip } from '@/components/ui/Tooltip';
import { useResizableNavigation } from '@/components/useResizableNavigation';

export interface NavigationRailProps { items: NavigationItem[]; activeId: string; collapsed: boolean; onCollapsedChange: (collapsed: boolean) => void; footer?: ReactNode; }

export function NavigationRail({ items, activeId, collapsed, onCollapsedChange, footer }: NavigationRailProps) {
  const { t } = useTranslation();
  const resize = useResizableNavigation();
  const width = collapsed ? 72 : resize.width;
  const toggleLabel = collapsed ? t('common.expandNavigation') : t('common.collapseNavigation');
  return (
    <aside className="relative hidden h-dvh shrink-0 flex-col bg-subtle p-4 shadow-floating lg:flex" style={{ width }}>
      <div className={collapsed ? 'flex justify-center' : 'flex justify-between'}>
        <Logo variant={collapsed ? 'mark' : 'full'} />
      </div>
      {!collapsed ? <p className="mt-6 text-overline font-medium text-muted">{t('navigation.workspace')}</p> : null}
      <NavigationMenu items={items} activeId={activeId} collapsed={collapsed} />
      {!collapsed && footer ? <div className="pb-3">{footer}</div> : null}
      <div className="border-t border-border pt-4">
        <Tooltip label={toggleLabel}>
          <button type="button" aria-label={toggleLabel} onClick={() => onCollapsedChange(!collapsed)} className="grid size-10 place-items-center rounded-lg text-muted hover:bg-surface focus-visible:outline-2 focus-visible:outline-focus">
            {collapsed ? <CaretDoubleRight aria-hidden className="size-5" /> : <CaretDoubleLeft aria-hidden className="size-5" />}
          </button>
        </Tooltip>
      </div>
      {!collapsed ? (
        <div role="separator" aria-orientation="vertical" aria-label={t('common.resizeNavigation')} aria-valuemin={resize.minWidth} aria-valuemax={resize.maxWidth} aria-valuenow={resize.width} tabIndex={0} onPointerDown={resize.onPointerDown} onKeyDown={resize.onKeyDown} className="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-transparent hover:bg-focus/40 focus:bg-focus/40 focus-visible:outline-none" />
      ) : null}
    </aside>
  );
}

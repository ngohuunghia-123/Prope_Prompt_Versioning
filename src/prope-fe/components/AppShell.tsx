import { useCallback, useState, type CSSProperties, type ReactNode } from 'react';
import type { NavigationItem } from '@/components/NavigationMenu';
import { NavigationRail } from '@/components/NavigationRail';
import { TopBar, type BreadcrumbItem } from '@/components/TopBar';
import type { TabItem } from '@/components/Tabs';
import { DashboardContext, type DashboardFilterValues } from '@/components/DashboardToolbarContext';

export interface AppShellProps {
  items?: NavigationItem[];
  activeId: string;
  breadcrumbs: BreadcrumbItem[];
  tabs?: TabItem[];
  activeTab?: string;
  onTabChange?: (value: string) => void;
  contextNavigation?: ReactNode;
  action?: ReactNode;
  account?: ReactNode;
  compactAccount?: ReactNode;
  children: ReactNode;
}

export function AppShell({ items, activeId, breadcrumbs, tabs, activeTab, onTabChange, contextNavigation, action, account, compactAccount, children }: AppShellProps) {
  const [collapsed, setCollapsedState] = useState(() => localStorage.getItem('prope-navigation-collapsed') === 'true');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [navigationWidth, setNavigationWidth] = useState(72);
  const [toolbarNode, setToolbarNode] = useState<ReactNode>(null);
  const [filters, setFilters] = useState<DashboardFilterValues>({ search: '', status: 'all' });
  const setCollapsed = useCallback((next: boolean) => { setCollapsedState(next); localStorage.setItem('prope-navigation-collapsed', String(next)); }, []);
  const setMobileOpen = useCallback((next: boolean) => setDrawerOpen(next), []);

  const updateFilters = useCallback((partial: Partial<DashboardFilterValues>) => {
    setFilters((prev) => ({ ...prev, ...partial }));
  }, []);

  return (
    <DashboardContext.Provider value={{ toolbarNode, setToolbarNode, filters: { ...filters, setSearch: (v: string) => updateFilters({ search: v }), setStatus: (v: string) => updateFilters({ status: v }) } }}>
      <div className="flex min-h-dvh bg-canvas text-ink" style={{ '--workspace-navigation-width': `${navigationWidth}px` } as CSSProperties}>
        <NavigationRail items={items} activeId={activeId} collapsed={collapsed} onCollapsedChange={setCollapsed} mobileOpen={drawerOpen} onMobileOpenChange={setMobileOpen} onWidthChange={setNavigationWidth} footer={account} compactFooter={compactAccount} />
        <div className="min-w-0 flex-1">
          <TopBar breadcrumbs={breadcrumbs} tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} action={action} toolbar={toolbarNode} onOpenNavigation={() => setMobileOpen(true)} />
          {contextNavigation ? <div className="border-b border-border bg-canvas px-4 sm:px-6">{contextNavigation}</div> : null}
          <main className="min-w-0 p-4 sm:p-6 lg:p-8">{children}</main>
        </div>
      </div>
    </DashboardContext.Provider>
  );
}

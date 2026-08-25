import { useCallback, useState, type CSSProperties, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import type { NavigationItem } from '@/components/NavigationMenu';
import { NavigationRail } from '@/components/NavigationRail';
import { TopBar, type BreadcrumbItem } from '@/components/TopBar';
import type { TabItem } from '@/components/Tabs';
import { DashboardContext, type DashboardFilterValues } from '@/components/DashboardToolbarContext';
import { FloatingAgentProvider } from '@/features/floating-agent/FloatingAgentProvider';
import { FloatingMascot } from '@/features/floating-agent/FloatingMascot';
import { cn } from '@/lib/cn';
import { useSurfaceEnter } from '@/lib/useSurfaceEnter';
import { AgentInteractionShield } from '@/features/chat/components/AgentInteractionShield';
import { ProductTourProvider } from '@/features/product-tour/ProductTourProvider';

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
  hideTopBar?: boolean;
  lockContentViewport?: boolean;
  mainClassName?: string;
  children: ReactNode;
}

export function AppShell({ items, activeId, breadcrumbs, tabs, activeTab, onTabChange, contextNavigation, action, account, compactAccount, hideTopBar = false, lockContentViewport = false, mainClassName, children }: AppShellProps) {
  const { pathname } = useLocation();
  const surfaceRef = useSurfaceEnter<HTMLElement>(pathname);
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
      <FloatingAgentProvider>
        <ProductTourProvider collapsed={collapsed} mobileOpen={drawerOpen} onCollapsedChange={setCollapsed} onMobileOpenChange={setMobileOpen}>
          <div className={cn('flex min-h-dvh bg-canvas text-ink', lockContentViewport && 'navigation:h-dvh navigation:min-h-0 navigation:overflow-hidden')} style={{ '--workspace-navigation-width': `${navigationWidth}px` } as CSSProperties}>
            <NavigationRail items={items} activeId={activeId} collapsed={collapsed} onCollapsedChange={setCollapsed} mobileOpen={drawerOpen} onMobileOpenChange={setMobileOpen} onWidthChange={setNavigationWidth} footer={account} compactFooter={compactAccount} />
            <div className={cn('relative min-w-0 flex-1', lockContentViewport && 'navigation:flex navigation:min-h-0 navigation:flex-col navigation:overflow-hidden')}>
              <AgentInteractionShield />
              {hideTopBar ? null : <TopBar breadcrumbs={breadcrumbs} tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} action={action} toolbar={toolbarNode} onOpenNavigation={() => setMobileOpen(true)} />}
              {contextNavigation ? <div className="border-b border-border bg-canvas px-4 sm:px-6">{contextNavigation}</div> : null}
              <main ref={surfaceRef} className={cn('min-w-0 p-4 sm:p-6 lg:p-8', lockContentViewport && 'navigation:min-h-0 navigation:flex-1 navigation:overflow-hidden', mainClassName)}>{children}</main>
            </div>
          </div>
          <FloatingMascot />
        </ProductTourProvider>
      </FloatingAgentProvider>
    </DashboardContext.Provider>
  );
}

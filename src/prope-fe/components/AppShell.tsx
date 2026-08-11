import { useCallback, useState, type ReactNode } from 'react';
import type { NavigationItem } from '@/components/NavigationMenu';
import { NavigationRail } from '@/components/NavigationRail';
import { TopBar } from '@/components/TopBar';
import { useTheme } from '@/lib/useTheme';

export interface AppShellProps { items?: NavigationItem[]; activeId: string; title: string; description?: string; action?: ReactNode; account?: ReactNode; compactAccount?: ReactNode; children: ReactNode; }

export function AppShell({ items, activeId, title, description, action, account, compactAccount, children }: AppShellProps) {
  const [collapsed, setCollapsedState] = useState(() => localStorage.getItem('prope-navigation-collapsed') === 'true');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { theme, setTheme } = useTheme();
  const setCollapsed = useCallback((next: boolean) => { setCollapsedState(next); localStorage.setItem('prope-navigation-collapsed', String(next)); }, []);
  const setMobileOpen = useCallback((next: boolean) => setDrawerOpen(next), []);
  return (
    <div className="flex min-h-dvh bg-canvas text-ink">
      <NavigationRail items={items} activeId={activeId} collapsed={collapsed} onCollapsedChange={setCollapsed} mobileOpen={drawerOpen} onMobileOpenChange={setMobileOpen} footer={account} compactFooter={compactAccount} />
      <div className="min-w-0 flex-1">
        <TopBar title={title} description={description} action={action} theme={theme} onThemeChange={setTheme} onOpenNavigation={() => setMobileOpen(true)} />
        <main className="min-w-0 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}

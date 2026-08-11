import { useState, type ReactNode } from 'react';
import { Logo } from '@/components/Logo';
import { NavigationMenu, type NavigationItem } from '@/components/NavigationMenu';
import { NavigationRail } from '@/components/NavigationRail';
import { TopBar } from '@/components/TopBar';
import { Drawer } from '@/components/ui/Drawer';
import { useTheme } from '@/lib/useTheme';

export interface AppShellProps { items: NavigationItem[]; activeId: string; title: string; description?: string; action?: ReactNode; account?: ReactNode; children: ReactNode; }

export function AppShell({ items, activeId, title, description, action, account, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { theme, setTheme } = useTheme();
  return (
    <div className="flex min-h-dvh bg-canvas text-ink">
      <NavigationRail items={items} activeId={activeId} collapsed={collapsed} onCollapsedChange={setCollapsed} footer={account} />
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Logo className="mb-4" />
        <NavigationMenu items={items} activeId={activeId} onNavigate={() => setDrawerOpen(false)} />
        {account}
      </Drawer>
      <div className="min-w-0 flex-1">
        <TopBar title={title} description={description} action={action} theme={theme} onThemeChange={setTheme} onOpenNavigation={() => setDrawerOpen(true)} />
        <main className="min-w-0 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}

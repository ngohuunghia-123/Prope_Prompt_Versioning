import { SidebarSimple } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import { Logo } from '@/components/Logo';
import { NavigationCompactItem } from '@/components/NavigationCompactItem';
import { NavigationModeTabs } from '@/components/NavigationModeTabs';
import type { NavigationMode } from '@/components/navigationTypes';
import { useNavigationHomeData } from '@/components/useNavigationHomeData';
import { FloatingAgentNavigationToggle } from '@/features/floating-agent/FloatingAgentNavigationToggle';

export interface NavigationCompactProps {
  activeId: string;
  account?: ReactNode;
  mode: NavigationMode;
  onExpand: () => void;
  onModeChange: (mode: NavigationMode) => void;
}

export function NavigationCompact({ activeId = '', account, mode, onExpand, onModeChange }: NavigationCompactProps) {
  const { t } = useTranslation();
  const { groups, supportLinks } = useNavigationHomeData();
  return (
    <div aria-label={t('navigation.advanced.collapsedLabel')} className="flex h-full flex-col items-center justify-between px-1 py-2.5">
      <div className="flex flex-col items-center gap-3">
        <a href="/app/home" aria-label={t('common.propeHome')}><Logo variant="mark" /></a>
        <button type="button" onClick={onExpand} aria-label={t('common.expandNavigation')} aria-expanded={false} title={t('common.expandNavigation')} className="grid size-8 shrink-0 cursor-pointer place-items-center rounded-navigation-control bg-transparent p-0 text-navigation-icon shadow-none transition-colors hover:bg-surface/55 hover:text-navigation-active focus-visible:outline-2 focus-visible:outline-focus"><SidebarSimple aria-hidden className="size-navigation-icon-large" /></button>
        <NavigationModeTabs compact mode={mode} onModeChange={(nextMode) => { onExpand(); onModeChange(nextMode); }} />
        <div className="flex flex-col items-center gap-3">{groups.map((group) => <NavigationCompactItem key={group.id} href={group.items[0]?.href ?? '/app/home'} icon={group.icon} label={group.compactLabel} active={activeId === group.id || activeId.startsWith(`${group.id}/`)} onNavigate={() => onModeChange('home')} />)}</div>
      </div>
      <div className="flex flex-col items-center gap-3">
        <FloatingAgentNavigationToggle />
        <div className="flex flex-col items-center gap-3">{supportLinks.map((item) => <NavigationCompactItem key={item.id} href={item.href} icon={item.icon} label={item.label} active={activeId === item.id || activeId.startsWith(`${item.id}/`)} onNavigate={() => onModeChange('home')} />)}</div>
        {account}
      </div>
    </div>
  );
}

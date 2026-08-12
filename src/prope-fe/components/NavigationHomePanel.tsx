import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { NavigationMenu, type NavigationItem } from '@/components/NavigationMenu';
import { useNavigationHomeData } from '@/components/useNavigationHomeData';

export interface NavigationHomePanelProps { activeId: string; items?: NavigationItem[]; account?: ReactNode; }

export function NavigationHomePanel({ activeId, items, account }: NavigationHomePanelProps) {
  const { t } = useTranslation();
  const { groups, supportLinks } = useNavigationHomeData(items);
  return (
    <section aria-label={t('navigation.advanced.home.label')} className="flex h-full min-h-0 animate-navigation-panel flex-col overflow-hidden pt-1">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overflow-x-hidden pb-3 pr-1 pt-1.5 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
        {groups.map((group) => <NavigationMenu key={group.id} label={group.label} items={group.items} activeId={activeId} />)}
      </div>
      <footer className="grid shrink-0 gap-1 border-t border-border/60 bg-navigation-surface pt-2.5">
        {supportLinks.map(({ id, label, href, icon }) => <Link key={id} to={href} className="flex min-h-8 min-w-0 items-center gap-2 rounded-navigation-control px-2 text-body text-link transition-colors hover:bg-surface/55 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"><span className="shrink-0 text-secondary">{icon}</span><span className="truncate">{label}</span></Link>)}
        {account ?? <Link to="/app/account" className="mt-1 flex min-h-13 min-w-0 items-center gap-2.5 rounded-navigation-panel bg-canvas p-2.5 text-ink shadow-inset transition-colors hover:bg-surface hover:text-link focus-visible:outline-2 focus-visible:outline-focus"><span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-full bg-navigation-avatar text-overline font-bold">LP</span><span className="min-w-0"><strong className="block truncate text-navigation-strong font-semibold">{t('navigation.advanced.home.accountName')}</strong><span className="block truncate text-overline text-muted">{t('navigation.advanced.home.accountPlan')}</span></span></Link>}
      </footer>
    </section>
  );
}

import { CaretRight, List } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Tabs, type TabItem } from '@/components/Tabs';
import { cn } from '@/lib/cn';

export interface BreadcrumbItem { label: string; href?: string; icon?: ReactNode; }
export interface TopBarProps { breadcrumbs: BreadcrumbItem[]; tabs?: TabItem[]; activeTab?: string; onTabChange?: (value: string) => void; action?: ReactNode; toolbar?: ReactNode; onOpenNavigation: () => void; }

export function TopBar({ breadcrumbs, tabs, activeTab, onTabChange, action, toolbar, onOpenNavigation }: TopBarProps) {
  const { t } = useTranslation();
  {/* Opaque background, deliberately not translucent: the top bar is the
      scroll boundary for the whole content column, and a 5%-translucent
      fill let whatever scrolled beneath it — long prompt bodies, the
      block/xml toggle — bleed through as ghost text over the breadcrumbs.
      With a solid fill the backdrop filter has nothing to blend, so it
      goes too. */}
  return (
    <header className={cn('sticky top-0 z-30 shrink-0 border-b border-border bg-canvas px-4 pt-2 sm:px-6', tabs ? 'navigation:pb-2' : 'pb-2')}>
      <div className="flex min-h-10 items-center gap-3">
        <button type="button" onClick={onOpenNavigation} aria-label={t('common.openNavigation')} className="grid size-10 shrink-0 cursor-pointer place-items-center rounded-lg text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus navigation:hidden"><List aria-hidden className="size-6" /></button>
        <nav aria-label={t('common.breadcrumb')} className="min-w-0 flex-1"><ol className="flex min-w-0 items-center gap-1 text-body">{breadcrumbs.map((item, index) => <li key={`${item.label}-${index}`} className="flex min-w-0 items-center gap-1">{index > 0 ? <CaretRight aria-hidden className="size-4 shrink-0 text-muted" /> : null}{item.icon ? <span aria-hidden className="mr-1 text-secondary">{item.icon}</span> : null}{item.href ? <Link to={item.href} className="truncate text-muted hover:text-link focus-visible:outline-2 focus-visible:outline-focus">{item.label}</Link> : <span aria-current="page" className="truncate font-medium text-ink">{item.label}</span>}</li>)}</ol></nav>
        <div id="topbar-actions" className="flex shrink-0 items-center gap-2">{action}</div>
      </div>
      {/* The context tabs render above the content column on wide screens
          (the prompt-detail view owns that placement); up here they only
          serve the stacked mobile layout, where the version rail sits
          between the top bar and the content otherwise. */}
      {tabs && activeTab && onTabChange ? <div className="navigation:hidden"><Tabs items={tabs} value={activeTab} onValueChange={onTabChange} label={t('common.contextNavigation')} /></div> : null}
      {toolbar ? <div className="border-b border-border">{toolbar}</div> : null}
    </header>
  );
}

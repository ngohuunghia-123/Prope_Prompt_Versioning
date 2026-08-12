import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavigationCompact } from '@/components/NavigationCompact';
import { NavigationExpanded } from '@/components/NavigationExpanded';
import type { NavigationItem } from '@/components/NavigationMenu';
import { useNavigationChat } from '@/components/useNavigationChat';
import { useNavigationMode } from '@/components/useNavigationMode';
import { useResizableNavigation } from '@/components/useResizableNavigation';
import { useDialogFocus } from '@/components/ui/useDialogFocus';
import { cn } from '@/lib/cn';

export interface NavigationRailProps {
  items?: NavigationItem[];
  activeId: string;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  mobileOpen?: boolean;
  onMobileOpenChange?: (open: boolean) => void;
  onWidthChange?: (width: number) => void;
  footer?: ReactNode;
  compactFooter?: ReactNode;
}

export function NavigationRail({ items, activeId, collapsed, onCollapsedChange, mobileOpen = false, onMobileOpenChange, onWidthChange, footer, compactFooter }: NavigationRailProps) {
  const { t } = useTranslation();
  const { mode, setMode } = useNavigationMode();
  const chat = useNavigationChat();
  const resize = useResizableNavigation(collapsed, onCollapsedChange);
  const [isExpanding, setIsExpanding] = useState(false);
  const closeMobile = useCallback(() => onMobileOpenChange?.(false), [onMobileOpenChange]);
  const focusRef = useDialogFocus(mobileOpen, closeMobile, '[data-mode][aria-current="page"]');
  useEffect(() => {
    if (mode === 'search' && !collapsed) requestAnimationFrame(() => document.querySelector<HTMLInputElement>('[data-navigation-search-input]')?.focus());
  }, [collapsed, mode]);
  const width = collapsed ? 72 : resize.width;
  useEffect(() => onWidthChange?.(width), [onWidthChange, width]);
  const expandImmediately = () => {
    setIsExpanding(true);
    onCollapsedChange(false);
    requestAnimationFrame(() => setIsExpanding(false));
  };
  return (
    <>
      <aside aria-label={t('navigation.advanced.workspaceLabel')} className={cn('fixed inset-y-0 left-0 z-40 flex h-dvh translate-x-[var(--navigation-translate)] overflow-visible bg-navigation-surface shadow-navigation transition-[transform,width] duration-(--prope-motion-duration-base) ease-standard [width:var(--navigation-width)] max-navigation:![width:var(--container-navigation-mobile)] navigation:sticky navigation:top-0 navigation:z-20 navigation:translate-x-0', (resize.isResizing || isExpanding) && 'transition-none')} style={{ '--navigation-width': `${width}px`, '--navigation-translate': mobileOpen ? '0%' : 'var(--prope-navigation-offscreen)' } as CSSProperties}>
        <div ref={focusRef} className="h-full w-full">
          <div className={cn('h-full', collapsed && 'navigation:hidden')}><NavigationExpanded items={items} activeId={activeId} account={footer} mode={mode} chatInput={chat.input} messages={chat.messages} thinking={chat.thinking} onCollapse={() => onCollapsedChange(true)} onModeChange={setMode} onChatInputChange={chat.setInput} onSendMessage={chat.sendMessage} /></div>
          {collapsed ? <div className="hidden h-full navigation:block"><NavigationCompact activeId={activeId} account={compactFooter} items={items} mode={mode} onExpand={expandImmediately} onModeChange={(nextMode) => { setMode(nextMode); requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-mode="${nextMode}"]`)?.focus()); }} /></div> : null}
        </div>
        {!collapsed ? <div role="separator" aria-label={t('common.resizeNavigation')} aria-orientation="vertical" aria-valuemin={resize.minWidth} aria-valuemax={resize.maxWidth} aria-valuenow={resize.width} tabIndex={0} onPointerDown={resize.onPointerDown} onKeyDown={resize.onKeyDown} className={cn('absolute -right-2 inset-y-0 z-30 hidden w-4 cursor-col-resize touch-none navigation:block after:absolute after:left-1.5 after:top-1/2 after:h-12 after:w-1 after:-translate-y-1/2 after:rounded-full after:bg-transparent after:transition-transform hover:after:bg-secondary focus:after:bg-secondary focus-visible:outline-2 focus-visible:outline-focus', resize.isResizing && 'after:bg-secondary', resize.isMagnetic && 'after:scale-y-125 after:bg-secondary')} /> : null}
      </aside>
      <button type="button" aria-label={t('common.close')} onClick={closeMobile} className={cn('fixed inset-0 z-35 block border-0 bg-ink/30 opacity-0 invisible transition-[opacity,visibility] duration-(--prope-motion-duration-base) navigation:hidden', mobileOpen && 'visible opacity-100')} />
    </>
  );
}

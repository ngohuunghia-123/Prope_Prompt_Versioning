import { useLayoutEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { useRovingTabs } from '@/components/useRovingTabs';

export interface TabItem { value: string; label: string; }
export interface TabsProps { items: TabItem[]; value: string; onValueChange: (value: string) => void; label: string; className?: string; }

export function Tabs({ items, value, onValueChange, label, className }: TabsProps) {
  const { onKeyDown, setRef, refs } = useRovingTabs(items.map((item) => item.value), value, onValueChange);
  const tabListRef = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState({ width: 0, x: 0 });

  useLayoutEffect(() => {
    const tabList = tabListRef.current;
    const updateIndicator = () => {
      const activeTab = refs.current.get(value);
      if (!activeTab) return;
      setIndicator({ width: activeTab.offsetWidth, x: activeTab.offsetLeft });
    };
    updateIndicator();
    const observer = tabList ? new ResizeObserver(updateIndicator) : undefined;
    if (tabList) observer?.observe(tabList);
    return () => observer?.disconnect();
  }, [items, refs, value]);

  return (
    <div ref={tabListRef} role="tablist" aria-label={label} className={cn('relative flex flex-wrap items-end gap-6 border-b border-border', className)}>
      <span aria-hidden className="pointer-events-none absolute bottom-0 left-0 h-0.5 rounded-full bg-secondary transition-[transform,width] duration-(--prope-motion-duration-base) ease-standard" style={{ width: indicator.width, transform: `translateX(${indicator.x}px)` }} />
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button key={item.value} ref={setRef(item.value)} type="button" role="tab" aria-selected={active} tabIndex={active ? 0 : -1} onKeyDown={onKeyDown} onClick={() => onValueChange(item.value)} className={cn('relative z-10 flex min-h-10 cursor-pointer items-center px-3 text-caption font-medium text-muted transition-colors focus-visible:outline-2 focus-visible:outline-focus', active && 'text-link')}>
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

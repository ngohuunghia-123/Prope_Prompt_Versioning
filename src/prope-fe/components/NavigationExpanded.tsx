import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { gsap } from 'gsap';
import { NavigationBrandHeader } from '@/components/NavigationBrandHeader';
import { NavigationExpandedView } from '@/components/NavigationExpandedView';
import type { NavigationItem } from '@/components/NavigationMenu';
import type { NavigationMode } from '@/components/navigationTypes';
import { animateNavigationSwap } from '@/lib/motion';

export interface NavigationExpandedProps {
  activeId: string;
  items?: NavigationItem[];
  account?: ReactNode;
  mode: NavigationMode;
  onCollapse: () => void;
  onModeChange: (mode: NavigationMode) => void;
}

export function NavigationExpanded({ activeId, items, account, mode, onCollapse, onModeChange }: NavigationExpandedProps) {
  const isSettings = activeId.startsWith('settings/');
  const incomingRef = useRef<HTMLDivElement>(null);
  const outgoingRef = useRef<HTMLDivElement>(null);
  const previousIsSettings = useRef(isSettings);
  const [outgoingIsSettings, setOutgoingIsSettings] = useState<boolean | null>(null);

  useLayoutEffect(() => {
    const changedPanel = previousIsSettings.current !== isSettings;
    previousIsSettings.current = isSettings;
    if (changedPanel) setOutgoingIsSettings(!isSettings);
  }, [isSettings]);

  useLayoutEffect(() => {
    if (outgoingIsSettings === null || !incomingRef.current || !outgoingRef.current) return;
    const incoming = incomingRef.current;
    const outgoing = outgoingRef.current;
    const context = gsap.context(() => {
      animateNavigationSwap(outgoing, incoming, isSettings, () => setOutgoingIsSettings(null));
    });
    return () => {
      context.revert();
      gsap.set([outgoing, incoming], { clearProps: 'all' });
    };
  }, [isSettings, outgoingIsSettings]);

  const viewProps = { activeId, items, mode, onModeChange };

  return (
    <div className="flex h-full min-w-0 max-w-full flex-col overflow-hidden">
      <header className="shrink-0 px-4 pt-2.5">
        <NavigationBrandHeader onCollapse={onCollapse} />
      </header>
      <div className="relative min-h-0 flex-1 overflow-hidden">
        {outgoingIsSettings !== null ? (
          <div ref={outgoingRef} className="absolute inset-0 bg-navigation-surface">
            <NavigationExpandedView {...viewProps} isSettings={outgoingIsSettings} />
          </div>
        ) : null}
        <div ref={incomingRef} className={outgoingIsSettings === null ? 'h-full' : 'absolute inset-0 bg-navigation-surface'}>
          <NavigationExpandedView {...viewProps} isSettings={isSettings} />
        </div>
      </div>
      {(isSettings || mode === 'home') && account ? <footer className="mx-4 shrink-0 border-t border-border/60 bg-navigation-surface pb-2.5 pt-2.5">{account}</footer> : null}
    </div>
  );
}

import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface BottomActionDockProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function BottomActionDock({ children, className, ...props }: BottomActionDockProps) {
  return (
    <div className={cn('fixed inset-x-0 bottom-0 z-30 border-t border-border bg-canvas/95 p-3 backdrop-blur-sm navigation:left-[var(--workspace-navigation-width)]', className)} {...props}>
      <div className="flex w-full flex-wrap items-center justify-end gap-2">
        {children}
      </div>
    </div>
  );
}

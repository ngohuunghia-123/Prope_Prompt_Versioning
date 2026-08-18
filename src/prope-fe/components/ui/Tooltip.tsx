import type { ReactElement } from 'react';
import { cn } from '@/lib/cn';

export interface TooltipProps { label: string; children: ReactElement; side?: 'top' | 'right'; className?: string; }

export function Tooltip({ label, children, side = 'top', className }: TooltipProps) {
  return (
    <span className={cn('group relative inline-flex', className)}>
      {children}
      <span role="tooltip" className={cn('pointer-events-none absolute z-50 rounded-md bg-ink px-2 py-1 whitespace-nowrap text-inverse opacity-0 shadow-floating transition-opacity group-focus-within:opacity-100 group-hover:opacity-100', side === 'top' ? 'bottom-full left-1/2 mb-2 -translate-x-1/2' : 'left-full top-1/2 ml-2 -translate-y-1/2')}>
        <span className="text-caption">{label}</span>
      </span>
    </span>
  );
}

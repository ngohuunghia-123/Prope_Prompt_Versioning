import type { ReactElement } from 'react';

export interface TooltipProps { label: string; children: ReactElement; }

export function Tooltip({ label, children }: TooltipProps) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-40 mb-2 -translate-x-1/2 rounded-md bg-ink px-2 py-1 text-caption whitespace-nowrap text-inverse opacity-0 shadow-floating transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        {label}
      </span>
    </span>
  );
}

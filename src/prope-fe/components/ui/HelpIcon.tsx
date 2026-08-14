import { Info } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { useState } from 'react';
import { cn } from '@/lib/cn';

export interface HelpIconProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

export function HelpIcon({ title, children, className }: HelpIconProps) {
  const [open, setOpen] = useState(false);
  return (
    <span className={cn('group relative inline-flex', className)}>
      <button
        type="button"
        aria-label="Help"
        aria-expanded={open}
        className="inline-flex cursor-pointer text-muted transition-colors hover:text-link focus-visible:outline-2 focus-visible:outline-focus"
        onClick={() => setOpen((v) => !v)}
        onBlur={(e) => {
          if (!e.currentTarget.closest('.group')?.contains(e.relatedTarget as Node)) {
            setOpen(false);
          }
        }}
      >
        <Info aria-hidden className="size-4" weight="regular" />
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-2 w-64 rounded-modal border border-border bg-surface p-3 shadow-floating"
        >
          {title ? (
            <p className="mb-1.5 font-semibold text-ink">{title}</p>
          ) : null}
          <div className="text-caption text-muted [&_p]:mb-1.5 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_strong]:text-ink">
            {children}
          </div>
        </span>
      )}
    </span>
  );
}

import { Info } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { useRef, useState } from 'react';
import { cn } from '@/lib/cn';

export interface HelpIconProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

export function HelpIcon({ title, children, className }: HelpIconProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  return (
    <span className={cn('group relative inline-flex', className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-label="Help"
        aria-expanded={open}
        className="inline-flex cursor-pointer text-muted transition-colors hover:text-link focus-visible:outline-2 focus-visible:outline-focus"
        onClick={() => {
          const bounds = buttonRef.current?.getBoundingClientRect();
          if (bounds) {
            setPosition({
              left: Math.min(bounds.left, window.innerWidth - 272),
              top: bounds.bottom + 8,
            });
          }
          setOpen((value) => !value);
        }}
        onBlur={(e) => {
          if (!e.currentTarget.closest('.group')?.contains(e.relatedTarget as Node)) {
            setOpen(false);
          }
        }}
      >
        <Info aria-hidden className="size-4" weight="regular" />
      </button>
      {open ? createPortal(
        <span role="tooltip" className="fixed z-50 w-64 rounded-modal border border-border bg-surface p-3 shadow-floating" style={position}>
          {title ? (
            <p className="mb-1.5 font-semibold text-ink">{title}</p>
          ) : null}
          <div className="text-caption text-muted [&_p]:mb-1.5 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_strong]:text-ink">
            {children}
          </div>
        </span>,
        document.body,
      ) : null}
    </span>
  );
}

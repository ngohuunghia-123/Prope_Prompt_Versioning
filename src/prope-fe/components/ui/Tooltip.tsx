import { useState, type ReactElement } from 'react';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

export interface TooltipProps { label: string; children: ReactElement; side?: 'top' | 'right'; className?: string; }

export function Tooltip({ label, children, side = 'top', className }: TooltipProps) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const visible = hovered || focused;
  const motion = useMotionPresence(visible, 'popover');
  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocusCapture={() => setFocused(true)}
      onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false); }}
    >
      {children}
      {motion.mounted ? (
        <span ref={(node) => { motion.surfaceRef.current = node; }} role="tooltip" className={cn('pointer-events-none absolute z-50 rounded-md bg-ink px-2 py-1 whitespace-nowrap text-inverse shadow-floating', side === 'top' ? 'bottom-full left-1/2 mb-2 -translate-x-1/2' : 'left-full top-1/2 ml-2 -translate-y-1/2')}>
          <span className="text-caption">{label}</span>
        </span>
      ) : null}
    </span>
  );
}

import { X } from '@phosphor-icons/react';
import { cva, type VariantProps } from 'class-variance-authority';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useEffect, useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { useDialogFocus } from '@/components/ui/useDialogFocus';

const drawerPanelVariants = cva(
  'flex h-full w-full flex-col bg-surface shadow-floating transition-transform duration-(--prope-motion-duration-slow) ease-(--prope-motion-ease-standard) motion-reduce:transition-none',
  {
    variants: {
      side: {
        left: 'mr-auto border-r border-border',
        right: 'ml-auto border-l border-border',
      },
      size: {
        compact: 'max-w-drawer',
        wide: 'max-w-2xl',
        // For content with an intrinsic width rather than a preferred one — the
        // trace graph is five columns of fixed-width boxes and cannot reflow
        // into `wide` without either shrinking labels below legibility or
        // handing the reader a horizontal scrollbar on every open.
        full: 'max-w-5xl',
      },
    },
    defaultVariants: { side: 'left', size: 'compact' },
  },
);

export interface DrawerProps extends VariantProps<typeof drawerPanelVariants> {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
  title?: string;
}

export function Drawer({ open, onClose, children, className, side = 'left', size = 'compact', title }: DrawerProps) {
  const { t } = useTranslation();
  const containerRef = useDialogFocus(open, onClose);
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    if (!open) return setEntered(false);
    const frame = window.requestAnimationFrame(() => setEntered(true));
    return () => window.cancelAnimationFrame(frame);
  }, [open]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 bg-ink/45" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={containerRef} role="dialog" aria-modal="true" aria-label={title} className={cn(drawerPanelVariants({ side, size }), entered ? 'translate-x-0' : side === 'right' ? 'translate-x-full' : '-translate-x-full', className)}>
        <div className="flex min-h-14 items-center justify-between border-b border-border px-5">
          {title ? <h2 className="text-body font-semibold text-ink">{title}</h2> : <span />}
          <button type="button" onClick={onClose} aria-label={t('common.close')} className="grid size-10 place-items-center rounded-full text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

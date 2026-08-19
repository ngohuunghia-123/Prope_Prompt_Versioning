import { X } from '@phosphor-icons/react';
import { cva, type VariantProps } from 'class-variance-authority';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { useDialogFocus } from '@/components/ui/useDialogFocus';
import { useMotionPresence } from '@/lib/useMotionPresence';

const drawerPanelVariants = cva(
  'flex h-full w-full flex-col bg-surface shadow-floating',
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
  const motion = useMotionPresence(open, side === 'right' ? 'drawer-right' : 'drawer-left');
  if (!motion.mounted) return null;
  return createPortal(
    <div
      ref={(node) => { motion.backdropRef.current = node; }}
      className={cn('fixed inset-0 z-50 bg-ink/45', !open && 'pointer-events-none')}
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div ref={(node) => { containerRef.current = node; motion.surfaceRef.current = node; }} role="dialog" aria-modal="true" aria-label={title} className={cn(drawerPanelVariants({ side, size }), className)}>
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

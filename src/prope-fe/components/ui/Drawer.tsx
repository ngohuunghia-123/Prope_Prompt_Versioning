import { X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { useDialogFocus } from '@/components/ui/useDialogFocus';

export interface DrawerProps { open: boolean; onClose: () => void; children: ReactNode; className?: string; }

export function Drawer({ open, onClose, children, className }: DrawerProps) {
  const { t } = useTranslation();
  const containerRef = useDialogFocus(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 bg-ink/45 lg:hidden" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={containerRef} role="dialog" aria-modal="true" className={cn('flex h-full w-full max-w-drawer flex-col bg-surface p-4 shadow-floating', className)}>
        <button type="button" onClick={onClose} aria-label={t('common.close')} className="ml-auto grid size-10 place-items-center rounded-full text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
          <X aria-hidden className="size-5" />
        </button>
        {children}
      </div>
    </div>,
    document.body,
  );
}

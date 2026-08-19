import { Info, X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';
import { useDialogFocus } from '@/components/ui/useDialogFocus';
import { useMotionPresence } from '@/lib/useMotionPresence';

export interface ModalProps {
  open: boolean; title: string; description: ReactNode; confirmLabel: string;
  onClose: () => void; onConfirm: () => void; destructive?: boolean; className?: string; children?: ReactNode; showCancel?: boolean;
  confirmDisabled?: boolean; confirmLoading?: boolean;
  confirmDisabledReason?: string;
  size?: 'default' | 'wide';
  icon?: ReactNode;
}

export function Modal({ open, title, description, confirmLabel, onClose, onConfirm, destructive = false, className, children, showCancel = true, confirmDisabled = false, confirmLoading = false, confirmDisabledReason, size = 'default', icon }: ModalProps) {
  const { t } = useTranslation();
  const containerRef = useDialogFocus(open, onClose);
  const motion = useMotionPresence(open, 'modal');
  if (!motion.mounted) return null;
  return createPortal(
    <div
      ref={(node) => { motion.backdropRef.current = node; }}
      className={cn('fixed inset-0 z-50 grid place-items-center bg-ink/45 p-4', !open && 'pointer-events-none')}
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        ref={(node) => { containerRef.current = node; motion.surfaceRef.current = node; }}
        role={destructive ? 'alertdialog' : 'dialog'}
        aria-modal="true"
        aria-labelledby="prope-modal-title"
        aria-describedby="prope-modal-description"
        className={cn(
          'flex max-h-full w-full flex-col gap-4 overflow-hidden rounded-modal bg-surface p-6 text-ink shadow-floating',
          size === 'wide' ? 'max-w-(--container-content)' : 'max-w-notification',
          className,
        )}
      >
        <div className="flex items-center justify-between gap-4">
          <span aria-hidden className="grid size-8 place-items-center rounded-full bg-info text-info-strong">{icon ?? <Info className="size-5" weight="bold" />}</span>
          <button type="button" onClick={onClose} aria-label={t('common.close')} className="grid size-10 place-items-center rounded-full text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <h2 id="prope-modal-title" className="text-heading-2 font-semibold">{title}</h2>
        <p id="prope-modal-description" className="text-body text-muted">{description}</p>
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">{children}</div>
        <div className={cn('mt-2 grid shrink-0 gap-2.5', showCancel ? 'grid-cols-2' : 'grid-cols-1')}>
          {showCancel ? <Button className="w-full" intent="neutral" onClick={onClose}>{t('common.cancel')}</Button> : null}
          <Button className="w-full" intent={destructive ? 'danger' : 'primary'} onClick={onConfirm} disabled={confirmDisabled} disabledReason={confirmDisabledReason} loading={confirmLoading}>{confirmLabel}</Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

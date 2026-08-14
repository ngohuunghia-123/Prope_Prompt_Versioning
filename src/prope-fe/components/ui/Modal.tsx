import { Info, X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';
import { useDialogFocus } from '@/components/ui/useDialogFocus';

export interface ModalProps {
  open: boolean; title: string; description: string; confirmLabel: string;
  onClose: () => void; onConfirm: () => void; destructive?: boolean; className?: string; children?: ReactNode; showCancel?: boolean;
  confirmDisabled?: boolean; confirmLoading?: boolean;
}

export function Modal({ open, title, description, confirmLabel, onClose, onConfirm, destructive = false, className, children, showCancel = true, confirmDisabled = false, confirmLoading = false }: ModalProps) {
  const { t } = useTranslation();
  const containerRef = useDialogFocus(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/45 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div
        ref={containerRef}
        role={destructive ? 'alertdialog' : 'dialog'}
        aria-modal="true"
        aria-labelledby="prope-modal-title"
        aria-describedby="prope-modal-description"
        className={cn('flex w-full max-w-notification flex-col gap-4 rounded-modal bg-surface p-6 text-ink shadow-floating', className)}
      >
        <div className="flex items-center justify-between gap-4">
          <span aria-hidden className="grid size-8 place-items-center rounded-full bg-info text-info-strong"><Info className="size-5" weight="bold" /></span>
          <button type="button" onClick={onClose} aria-label={t('common.close')} className="grid size-10 place-items-center rounded-full text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <h2 id="prope-modal-title" className="text-heading-2 font-semibold">{title}</h2>
        <p id="prope-modal-description" className="text-body text-muted">{description}</p>
        {children}
        <div className="mt-2 flex flex-wrap gap-2.5">
          {showCancel ? <Button intent="neutral" onClick={onClose}>{t('common.cancel')}</Button> : null}
          <Button intent={destructive ? 'danger' : 'primary'} onClick={onConfirm} disabled={confirmDisabled} loading={confirmLoading}>{confirmLabel}</Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

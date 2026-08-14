import { Info, X } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';
import { useDialogFocus } from '@/components/ui/useDialogFocus';

export interface ModalProps {
  open: boolean; title: string; description: string; confirmLabel: string;
  onClose: () => void; onConfirm: () => void; destructive?: boolean; className?: string;
  confirmDisabled?: boolean; confirmLoading?: boolean;
  /**
   * Optional body between the description and the buttons.
   *
   * Added for the review dialog, which has to collect a *reason* before it can
   * confirm: `request-changes` requires a comment, and approving a revision whose
   * evals failed requires an acknowledgement reason that is recorded on the
   * approval (ADR-0005). A confirm dialog that could only say yes or no would push
   * that field back onto the page behind it, where it is not obviously part of the
   * decision being taken.
   */
  children?: ReactNode;
}

export function Modal({ open, title, description, confirmLabel, onClose, onConfirm, destructive = false, confirmDisabled = false, confirmLoading = false, className, children }: ModalProps) {
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
          <Button intent="neutral" onClick={onClose}>{t('common.cancel')}</Button>
          <Button intent={destructive ? 'danger' : 'primary'} disabled={confirmDisabled} loading={confirmLoading} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

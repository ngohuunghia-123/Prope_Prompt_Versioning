import { X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { useDialogFocus } from '@/components/ui/useDialogFocus';
import { useMotionPresence } from '@/lib/useMotionPresence';

export interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  /** Rendered along the bottom edge, below the scroll region. */
  footer?: ReactNode;
  className?: string;
}

/**
 * A surface that rises from the bottom edge over the page it belongs to.
 *
 * **Not a `Modal`, and the difference is what it is for.** A modal is a
 * question: it takes the screen, it has a confirm and a cancel, and the flow
 * stops until somebody answers. This reports on work that is already running —
 * the form behind it is the thing being checked and stays visible, and there is
 * nothing to answer until the run finishes. **Not a `Drawer` either**: a drawer
 * comes from the side and is a place to put a second subject, and this has the
 * same subject as the page.
 *
 * It keeps the modal's manners where they protect somebody: focus is trapped
 * while it is up (`useDialogFocus` also binds Escape), and the backdrop takes
 * pointer events, so a second press of "Đánh giá" cannot start a second import
 * behind it.
 */
export function BottomSheet({ open, onClose, title, description, children, footer, className }: BottomSheetProps) {
  const { t } = useTranslation();
  const containerRef = useDialogFocus(open, onClose);
  const motion = useMotionPresence(open, 'sheet-bottom');
  if (!motion.mounted) return null;

  return createPortal(
    <div
      ref={(node) => { motion.backdropRef.current = node; }}
      className={cn('fixed inset-0 z-50 flex items-end justify-center bg-ink/45', !open && 'pointer-events-none')}
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        ref={(node) => { containerRef.current = node; motion.surfaceRef.current = node; }}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          // **Full width, like the edge it rises from.** A capped, centred panel
          // reads as a modal that lost its middle; a sheet is a second surface
          // attached to the bottom of the page, and attaching it means spanning
          // it. The prose inside is held to the page's own content width below,
          // so widening the panel does not widen the line length.
          //
          // Height is capped rather than set: the trace grows a row at a time
          // while the sheet is open, and a fixed height would leave it half
          // empty at the start of a run and clipped at the end.
          'flex max-h-[85vh] w-full flex-col rounded-t-modal border border-b-0 border-border bg-surface shadow-floating',
          className,
        )}
      >
        <div className="border-b border-border px-5 py-4">
          <div className="mx-auto flex w-full max-w-(--container-content) items-start justify-between gap-4">
            <div className="grid gap-1">
              <h2 className="text-body font-semibold text-ink">{title}</h2>
              {description ? <p className="text-caption leading-relaxed text-muted">{description}</p> : null}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t('common.close')}
              className="grid size-10 shrink-0 place-items-center rounded-full text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"
            >
              <X aria-hidden className="size-5" />
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto px-5 py-4">
          <div className="mx-auto w-full max-w-(--container-content)">{children}</div>
        </div>
        {footer ? (
          <div className="border-t border-border px-5 py-3">
            <div className="mx-auto w-full max-w-(--container-content)">{footer}</div>
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}

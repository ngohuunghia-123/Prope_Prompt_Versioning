import { CheckCircle, Info, WarningCircle, X } from '@phosphor-icons/react';
import { cva } from 'class-variance-authority';
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { gsap } from 'gsap';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { animatePresence } from '@/lib/motion';

type NotificationTone = 'success' | 'error' | 'info' | 'warning';
const notificationVariants = cva('flex w-full items-start gap-3 rounded-notification border px-4 py-notification-y shadow-notification', {
  variants: {
    tone: {
      success: 'border-border-success bg-success', error: 'border-danger-strong bg-danger', info: 'border-info-strong bg-info', warning: 'border-warning-strong bg-warning',
    },
  }, defaultVariants: { tone: 'success' },
});
const toneStyles: Record<NotificationTone, string> = { success: 'text-success-text', error: 'text-danger-text', info: 'text-info-strong', warning: 'text-warning-strong' };

export interface NotificationProps { tone?: NotificationTone; title: string; children: ReactNode; onDismiss?: () => void; className?: string; }

export function Notification({ tone = 'success', title, children, onDismiss, className }: NotificationProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLElement>(null);
  const [dismissing, setDismissing] = useState(false);
  const Icon = tone === 'success' ? CheckCircle : tone === 'info' ? Info : WarningCircle;
  useLayoutEffect(() => {
    if (!ref.current) return;
    const context = gsap.context(() => { if (ref.current) animatePresence(ref.current, 'toast', true); }, ref);
    return () => context.revert();
  }, []);
  const dismiss = () => {
    if (!ref.current || dismissing || !onDismiss) return;
    setDismissing(true);
    animatePresence(ref.current, 'toast', false, onDismiss);
  };
  return (
    <section ref={ref} aria-live="polite" className={cn(notificationVariants({ tone }), dismissing && 'pointer-events-none', className)}>
      <Icon aria-hidden weight="fill" className={cn('mt-0.5 size-6 shrink-0', toneStyles[tone])} />
      <div className="min-w-0 flex-1">
        <h3 className="font-sans text-body-large font-semibold text-ink">{title}</h3>
        <p className="mt-1 text-body text-muted">{children}</p>
      </div>
      {onDismiss ? (
        <button type="button" onClick={dismiss} aria-label={t('common.close')} className="grid size-8 shrink-0 place-items-center rounded-full text-muted hover:bg-surface/60 focus-visible:outline-2 focus-visible:outline-focus">
          <X aria-hidden className="size-4" />
        </button>
      ) : null}
    </section>
  );
}

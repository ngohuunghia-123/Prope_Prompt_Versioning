import { CheckCircle, Info, SpinnerGap, WarningCircle, X } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { useFloatingAgent } from '@/features/floating-agent/FloatingAgentContext';
import type { FloatingAgentEvent } from '@/features/floating-agent/types';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

const toneStyles = {
  progress: 'text-info-strong',
  success: 'text-success-text',
  warning: 'text-warning-text',
  tip: 'text-info-strong',
} as const;

function StatusIcon({ event }: { event: FloatingAgentEvent }) {
  if (event.type === 'progress') return <SpinnerGap aria-hidden className="size-5 animate-spin motion-reduce:animate-none" />;
  if (event.type === 'success') return <CheckCircle aria-hidden weight="fill" className="size-5" />;
  if (event.type === 'warning') return <WarningCircle aria-hidden weight="fill" className="size-5" />;
  return <Info aria-hidden weight="fill" className="size-5" />;
}

export function FloatingAgentBubble({ below, alignRight }: { below: boolean; alignRight: boolean }) {
  const { t } = useTranslation();
  const { expanded, activeEvent, dismiss } = useFloatingAgent();
  const motion = useMotionPresence(expanded && activeEvent !== null, 'popover');
  if (!motion.mounted || !activeEvent) return null;

  return (
    <section
      ref={(node) => { motion.surfaceRef.current = node; }}
      role={activeEvent.type === 'warning' ? 'alert' : 'status'}
      aria-live={activeEvent.type === 'warning' ? 'assertive' : 'polite'}
      className={cn('absolute z-10 w-(--container-floating-agent) rounded-panel border border-border bg-surface px-5 py-4 shadow-floating', below ? 'top-22' : 'bottom-12', alignRight ? 'right-0' : 'left-0')}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-sans text-body font-semibold text-ink">{t(activeEvent.titleKey)}</h2>
          <p className="mt-0.5 text-body text-muted">{t(activeEvent.messageKey)}</p>
          {activeEvent.progress !== undefined ? (
            <div className="mt-3" aria-label={t('floatingAgent.progressLabel', { progress: activeEvent.progress })}>
              <div className="h-1.5 overflow-hidden rounded-full bg-subtle">
                <div className="h-full rounded-full bg-info-strong transition-[width] duration-(--prope-motion-duration-base) motion-reduce:transition-none" style={{ width: `${activeEvent.progress}%` }} />
              </div>
              <span className="mt-1 block text-overline font-semibold text-muted">{activeEvent.progress}%</span>
            </div>
          ) : null}
          {activeEvent.action ? (
            <Link to={activeEvent.action.href} className="mt-2 inline-flex text-caption font-semibold text-link underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-focus">
              {t(activeEvent.action.labelKey)}
            </Link>
          ) : null}
        </div>
        {activeEvent.dismissible ? (
          <Button type="button" intent="ghost" size="floatingAgentIcon" onClick={() => dismiss(activeEvent.id)} aria-label={t('floatingAgent.dismiss')} className={cn('shrink-0', toneStyles[activeEvent.type])}>
            <X aria-hidden className="size-4" />
          </Button>
        ) : <span className={cn('grid size-9 shrink-0 place-items-center', toneStyles[activeEvent.type])}><StatusIcon event={activeEvent} /></span>}
      </div>
    </section>
  );
}

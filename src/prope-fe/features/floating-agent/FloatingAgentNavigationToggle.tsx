import { CheckCircle, Eye, EyeSlash, SpinnerGap } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { useFloatingAgent } from '@/features/floating-agent/FloatingAgentContext';
import { cn } from '@/lib/cn';

export function FloatingAgentNavigationToggle({ labelled = false }: { labelled?: boolean }) {
  const { t } = useTranslation();
  const { visible, activeEvent, runningCount, toggleVisible } = useFloatingAgent();
  const eventStatus = activeEvent?.type;
  const statusKey = runningCount > 0
    ? 'floatingAgent.hiddenRunning'
    : eventStatus === 'warning'
      ? 'floatingAgent.statusWarning'
      : eventStatus === 'success'
        ? 'floatingAgent.hiddenComplete'
        : 'floatingAgent.statusIdle';
  const actionLabel = t(visible ? 'floatingAgent.hide' : 'floatingAgent.show');

  return (
    <div className={cn('flex min-w-0 items-center', labelled && 'min-h-8 gap-2 rounded-navigation-control px-2 py-1.5 hover:bg-surface/55')}>
      {labelled ? (
        <span className="min-w-0 flex-1">
          <span className="block truncate text-body text-link">{actionLabel}</span>
          <span className="block truncate text-overline text-muted">{t(statusKey, { count: runningCount })}</span>
        </span>
      ) : null}
      <Button type="button" intent="ghost" size="floatingAgentIcon" aria-label={`${actionLabel}. ${t(statusKey, { count: runningCount })}`} aria-pressed={visible} title={actionLabel} onClick={toggleVisible} className="relative shrink-0 rounded-navigation-control text-navigation-icon">
        {visible ? <Eye aria-hidden className="size-navigation-icon" /> : <EyeSlash aria-hidden className="size-navigation-icon" />}
        {runningCount > 0 ? <SpinnerGap aria-hidden className="absolute -right-0.5 -top-0.5 size-3.5 animate-spin rounded-full bg-navigation-surface text-info-strong motion-reduce:animate-none" /> : null}
        {runningCount === 0 && eventStatus === 'warning' ? <span aria-hidden className="absolute -right-0.5 -top-0.5 size-3 rounded-full border-2 border-navigation-surface bg-warning-strong" /> : null}
        {runningCount === 0 && eventStatus === 'success' ? <CheckCircle aria-hidden weight="fill" className="absolute -right-0.5 -top-0.5 size-3.5 rounded-full bg-navigation-surface text-success-text" /> : null}
      </Button>
    </div>
  );
}

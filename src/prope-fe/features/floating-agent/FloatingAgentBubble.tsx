import { useTranslation } from 'react-i18next';
import { useFloatingAgent } from '@/features/floating-agent/FloatingAgentContext';
import { FloatingAgentTaskItem } from '@/features/floating-agent/FloatingAgentTaskItem';
import { FLOATING_AGENT_ASSETS } from '@/features/floating-agent/assets';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

export function FloatingAgentBubble({ below, alignRight }: { below: boolean; alignRight: boolean }) {
  const { t } = useTranslation();
  const { expanded, events } = useFloatingAgent();
  const motion = useMotionPresence(expanded, 'popover');
  if (!motion.mounted) return null;

  return (
    <section
      id="floating-agent-task-center"
      data-tour-id="background-tasks"
      ref={(node) => { motion.surfaceRef.current = node; }}
      aria-label={t('floatingAgent.taskCenter')}
      className={cn('absolute z-10 max-h-96 w-(--container-floating-agent) overflow-y-auto rounded-panel border border-border bg-surface p-4 shadow-floating', below ? 'top-12' : 'bottom-12', alignRight ? 'right-0' : 'left-0')}
    >
      <h2 className="font-sans text-body font-semibold text-ink">{t('floatingAgent.taskCenter')}</h2>
      {events.length === 0 ? (
        <div className="grid justify-items-center gap-2 py-5 text-center">
          <img src={FLOATING_AGENT_ASSETS.empty} alt="" className="size-20 object-contain" />
          <p className="text-caption text-muted">{t('floatingAgent.statusIdle')}</p>
        </div>
      ) : (
        <div className="mt-3 divide-y divide-border">
          {events.slice(0, 5).map((event) => <FloatingAgentTaskItem key={event.id} event={event} />)}
        </div>
      )}
    </section>
  );
}

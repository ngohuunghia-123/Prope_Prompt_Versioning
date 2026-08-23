import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { FLOATING_AGENT_ASSETS } from '@/features/floating-agent/assets';
import { FloatingAgentBubble } from '@/features/floating-agent/FloatingAgentBubble';
import { useFloatingAgent } from '@/features/floating-agent/FloatingAgentContext';
import { useFloatingMascotDrag } from '@/features/floating-agent/useFloatingMascotDrag';
import { cn } from '@/lib/cn';

export function FloatingMascot() {
  const { t } = useTranslation();
  const { visible, expanded, activeEvent, runningCount, setExpanded } = useFloatingAgent();
  const drag = useFloatingMascotDrag();
  useEffect(() => {
    if (!visible || !expanded) return;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') setExpanded(false); };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [expanded, setExpanded, visible]);
  if (!visible) return null;
  const bubbleBelow = drag.position.y < window.innerHeight / 2;
  const alignRight = drag.position.x > window.innerWidth / 2;

  return (
    <div className="fixed z-50 size-12" style={{ left: drag.position.x, top: drag.position.y }}>
      <FloatingAgentBubble below={bubbleBelow} alignRight={alignRight} />
      <Button
        type="button"
        intent="ghost"
        size="floatingAgentIcon"
        aria-label={t('floatingAgent.dragLabel')}
        aria-expanded={expanded}
        aria-controls="floating-agent-task-center"
        onClick={() => { if (!drag.moved.current) setExpanded(!expanded); drag.moved.current = false; }}
        onPointerDown={drag.onPointerDown}
        onPointerMove={drag.onPointerMove}
        onPointerUp={drag.onPointerUp}
        onPointerCancel={drag.onPointerCancel}
        className={cn('size-12 cursor-grab touch-none select-none overflow-visible rounded-full active:cursor-grabbing', drag.dragging && 'scale-105')}
      >
        {runningCount > 0 ? (
          <>
            <img src={FLOATING_AGENT_ASSETS.active} alt="" draggable={false} className="pointer-events-none size-12 object-contain motion-reduce:hidden" />
            <img src={FLOATING_AGENT_ASSETS.idle} alt="" draggable={false} className="pointer-events-none hidden size-12 object-contain motion-reduce:block" />
          </>
        ) : <img src={FLOATING_AGENT_ASSETS.idle} alt="" draggable={false} className="pointer-events-none size-12 object-contain" />}
      </Button>
      {activeEvent ? <span aria-hidden className={cn('pointer-events-none absolute right-0 top-0 size-3 rounded-full border-2 border-surface', activeEvent.type === 'warning' ? 'bg-warning-strong' : activeEvent.type === 'success' ? 'bg-success-strong' : 'bg-info-strong', activeEvent.type === 'progress' && 'animate-pulse motion-reduce:animate-none')} /> : null}
    </div>
  );
}

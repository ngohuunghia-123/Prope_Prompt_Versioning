import { CaretDown, CaretUp, Waveform } from '@phosphor-icons/react';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { FLOATING_AGENT_ASSETS } from '@/features/floating-agent/assets';
import { FloatingAgentBubble } from '@/features/floating-agent/FloatingAgentBubble';
import { useFloatingAgent } from '@/features/floating-agent/FloatingAgentContext';
import { useFloatingMascotDrag } from '@/features/floating-agent/useFloatingMascotDrag';
import { cn } from '@/lib/cn';

function openAgentChat() {
  if (window.location.hash !== '#chat') {
    window.history.pushState({ mode: 'chat' }, '', '#chat');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }
}

export function FloatingMascot() {
  const { t } = useTranslation();
  const { visible, expanded, activeEvent, setExpanded } = useFloatingAgent();
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
    <div className="fixed z-50 size-9" style={{ left: drag.position.x, top: drag.position.y }}>
      <FloatingAgentBubble below={bubbleBelow} alignRight={alignRight} />
      <Button
        type="button"
        intent="ghost"
        size="floatingAgentIcon"
        aria-label={t('floatingAgent.dragLabel')}
        aria-expanded={expanded}
        onClick={() => { if (!drag.moved.current) setExpanded(!expanded); drag.moved.current = false; }}
        onPointerDown={drag.onPointerDown}
        onPointerMove={drag.onPointerMove}
        onPointerUp={drag.onPointerUp}
        onPointerCancel={drag.onPointerCancel}
        className={cn('cursor-grab touch-none select-none overflow-visible active:cursor-grabbing', drag.dragging && 'scale-105')}
      >
        <img src={FLOATING_AGENT_ASSETS.mascot} alt="" draggable={false} className="pointer-events-none size-9 object-contain" />
      </Button>
      {activeEvent ? <span aria-hidden className={cn('pointer-events-none absolute right-0 top-0 size-2.5 rounded-full border-2 border-surface', activeEvent.type === 'warning' ? 'bg-warning-strong' : activeEvent.type === 'success' ? 'bg-success-strong' : 'bg-info-strong', activeEvent.type === 'progress' && 'animate-pulse motion-reduce:animate-none')} /> : null}
      <div className="absolute left-1/2 top-11 flex -translate-x-1/2 gap-2">
        <Button type="button" intent="neutral" size="floatingAgentIcon" onClick={openAgentChat} aria-label={t('floatingAgent.openChat')} title={t('floatingAgent.openChat')}>
          <Waveform aria-hidden className="size-4" />
        </Button>
        <Button type="button" intent="neutral" size="floatingAgentIcon" onClick={() => setExpanded(!expanded)} aria-label={t(expanded ? 'floatingAgent.collapse' : 'floatingAgent.expand')} title={t(expanded ? 'floatingAgent.collapse' : 'floatingAgent.expand')}>
          {expanded ? <CaretDown aria-hidden className="size-4" /> : <CaretUp aria-hidden className="size-4" />}
        </Button>
      </div>
    </div>
  );
}

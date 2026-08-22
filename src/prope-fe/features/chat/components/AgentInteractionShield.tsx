import { useTranslation } from 'react-i18next';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';

export function AgentInteractionShield() {
  const { t } = useTranslation();
  const { interacting } = useAgentSurface();
  if (!interacting) return null;
  return (
    <div className="absolute inset-0 z-30 grid cursor-wait place-items-center bg-surface/70 backdrop-blur-sm" role="status" aria-live="polite">
      <span className="rounded-control border border-border bg-surface px-4 py-2 text-caption font-semibold text-ink shadow-panel">{t('chat.interaction.applying')}</span>
    </div>
  );
}

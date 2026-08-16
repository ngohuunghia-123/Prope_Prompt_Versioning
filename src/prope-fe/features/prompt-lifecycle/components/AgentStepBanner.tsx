import { Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

/** The import stepper the agent drives, in the order the flow runs. */
const STEPS = ['paste', 'convert', 'duplicates', 'review', 'save'] as const;

/**
 * Where the agent thinks the import has got to.
 *
 * Rendered only once the agent has said something — an import somebody started
 * by hand has its own affordances and does not need a second progress model on
 * screen. It reports rather than controls: no step here is clickable, because
 * the agent describing the flow must never become the agent driving somebody
 * past a step they have not looked at.
 */
export function AgentStepBanner({ step }: { step: string | null }) {
  const { t } = useTranslation();
  const current = STEPS.indexOf(step as (typeof STEPS)[number]);
  if (current < 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-modal border border-border bg-surface px-4 py-2.5 shadow-panel">
      <span className="flex items-center gap-1.5 text-caption text-muted">
        <Sparkle aria-hidden className="size-4 text-secondary" />
        {t('lifecycle.newPrompt.agentSteps.label')}
      </span>
      <ol className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 p-0">
        {STEPS.map((name, index) => (
          <li
            key={name}
            aria-current={index === current ? 'step' : undefined}
            className={cn(
              'list-none rounded-full px-2 py-0.5 text-caption',
              index === current ? 'bg-secondary text-inverse' : index < current ? 'text-muted line-through' : 'text-muted',
            )}
          >
            {t(`lifecycle.newPrompt.agentSteps.${name}`)}
          </li>
        ))}
      </ol>
    </div>
  );
}

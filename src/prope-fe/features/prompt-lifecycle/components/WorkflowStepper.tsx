import { ArrowElbowDownLeft, Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { WorkflowStepButton } from '@/features/prompt-lifecycle/components/WorkflowStepButton';
import type { WorkflowStep, WorkflowStepId } from '@/features/prompt-lifecycle/types';

export interface WorkflowStepperProps { steps: WorkflowStep[]; currentId: WorkflowStepId; selectedId: WorkflowStepId; onSelect: (id: WorkflowStepId) => void; }

export function WorkflowStepper({ steps, currentId, selectedId, onSelect }: WorkflowStepperProps) {
  const { t } = useTranslation();
  const reasoningSteps = steps.filter((step) => step.result || step.status === 'running');
  return (
    <nav aria-label={t('lifecycle.workflow.timelineLabel')} className="rounded-modal border border-border bg-subtle p-4 shadow-inset">
      <header className="mb-4 flex items-start gap-3">
        <span className="relative grid size-9 shrink-0 place-items-center rounded-full bg-surface text-secondary shadow-panel">
          <Sparkle aria-hidden className="size-5" weight="duotone" />
          <span className="absolute inset-0 animate-ping rounded-full bg-secondary/30 motion-reduce:animate-none" />
        </span>
        <div>
          <h3 className="text-body font-semibold text-ink">{t('lifecycle.workflow.traceTitle')}</h3>
          <p className="mt-1 text-caption text-muted">{t('lifecycle.workflow.traceDescription')}</p>
        </div>
      </header>
      <div className="relative space-y-1">
        <div className="absolute left-4 top-0 h-full w-px bg-gradient-to-b from-secondary/40 via-border to-transparent" />
        {reasoningSteps.map((step, index) => (
          <div key={step.id} className="relative pl-9">
            <div className={`absolute left-2.5 top-3.5 z-10 flex size-3 items-center justify-center rounded-full ${step.status === 'running' ? 'bg-secondary' : step.status === 'passed' ? 'bg-success' : 'bg-muted/50'}`}>
              {step.status === 'passed' && <Sparkle aria-hidden className="size-2 text-surface" weight="fill" />}
            </div>
            <WorkflowStepButton
              step={step}
              current={step.id === currentId}
              selected={step.id === selectedId}
              onSelect={() => onSelect(step.id)}
              index={index + 1}
            />
          </div>
        ))}
        {reasoningSteps.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Sparkle aria-hidden className="mb-2 size-8 text-muted/40" weight="duotone" />
            <p className="text-caption text-muted">{t('lifecycle.workflow.noTraceYet')}</p>
          </div>
        )}
        <div className="mt-3 flex items-center gap-2 pl-9">
          <ArrowElbowDownLeft aria-hidden className="size-4 text-secondary" />
          <span className="text-caption text-muted">{t('lifecycle.workflow.thinkingIndicator')}</span>
        </div>
      </div>
    </nav>
  );
}

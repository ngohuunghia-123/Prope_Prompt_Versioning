import { Brain, Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { WorkflowStepButton } from '@/features/prompt-lifecycle/components/WorkflowStepButton';
import type { WorkflowStep, WorkflowStepId } from '@/features/prompt-lifecycle/types';

export interface WorkflowStepperProps { steps: WorkflowStep[]; currentId: WorkflowStepId; selectedId: WorkflowStepId; onSelect: (id: WorkflowStepId) => void; }

export function WorkflowStepper({ steps, currentId, selectedId, onSelect }: WorkflowStepperProps) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t('lifecycle.workflow.timelineLabel')} className="rounded-modal border border-border bg-subtle p-4 shadow-inset">
      <header className="mb-4 flex items-start gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface text-secondary shadow-panel"><Brain aria-hidden className="size-5" /></span><div><h3 className="text-body font-semibold text-ink">{t('lifecycle.workflow.traceTitle')}</h3><p className="mt-1 text-caption text-muted">{t('lifecycle.workflow.traceDescription')}</p></div></header>
      <ol className="relative grid gap-1 before:absolute before:bottom-5 before:left-4 before:top-5 before:w-px before:bg-border">
        {steps.map((step) => <li key={step.id} className="relative"><span aria-hidden className="absolute left-2.5 top-4 z-10 grid size-3 place-items-center rounded-full bg-subtle"><Sparkle className="size-3 text-secondary" weight={step.id === currentId ? 'fill' : 'regular'} /></span><WorkflowStepButton step={step} current={step.id === currentId} selected={step.id === selectedId} onSelect={() => onSelect(step.id)} /></li>)}
      </ol>
    </nav>
  );
}

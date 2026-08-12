import { useTranslation } from 'react-i18next';
import { WorkflowStepButton } from '@/features/prompt-lifecycle/components/WorkflowStepButton';
import type { WorkflowStep, WorkflowStepId } from '@/features/prompt-lifecycle/types';

const stages = ['prepare', 'engineer', 'evaluation', 'reviewer', 'canary'] as const;

export interface WorkflowStepperProps { steps: WorkflowStep[]; currentId: WorkflowStepId; selectedId: WorkflowStepId; onSelect: (id: WorkflowStepId) => void; }

export function WorkflowStepper({ steps, currentId, selectedId, onSelect }: WorkflowStepperProps) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t('lifecycle.workflow.timelineLabel')} className="rounded-modal border border-border bg-subtle p-4 shadow-inset">
      <div className="grid gap-5">
        {stages.map((stage) => {
          const stageSteps = steps.filter((step) => step.stage === stage);
          return <section key={stage} aria-labelledby={`stage-${stage}`}><h3 id={`stage-${stage}`} className="mb-2 text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t(`lifecycle.workflow.stages.${stage}`)}</h3><ol className="grid gap-1 border-l border-border pl-2">{stageSteps.map((step) => <li key={step.id}><WorkflowStepButton step={step} current={step.id === currentId} selected={step.id === selectedId} onSelect={() => onSelect(step.id)} /></li>)}</ol></section>;
        })}
      </div>
    </nav>
  );
}

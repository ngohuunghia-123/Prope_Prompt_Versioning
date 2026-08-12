import { useTranslation } from 'react-i18next';
import { WorkflowStatusIndicator } from '@/features/prompt-lifecycle/components/WorkflowStatusIndicator';
import type { WorkflowStep } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

export interface WorkflowStepButtonProps { step: WorkflowStep; selected: boolean; current: boolean; onSelect: () => void; }

export function WorkflowStepButton({ step, selected, current, onSelect }: WorkflowStepButtonProps) {
  const { t } = useTranslation();
  return (
    <button type="button" aria-current={current ? 'step' : undefined} aria-pressed={selected} onClick={onSelect} className={cn('grid w-full grid-cols-[auto_1fr] items-start gap-3 rounded-xl border border-transparent p-3 text-left transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus', selected && 'border-border bg-surface shadow-panel', step.status === 'skipped' && 'opacity-70')}>
      <WorkflowStatusIndicator status={step.status} compact />
      <span className="min-w-0"><strong className="block truncate text-body font-semibold text-ink">{t(`lifecycle.workflow.steps.${step.id}.title`)}</strong><span className="mt-1 block text-caption text-muted">{t(`lifecycle.workflow.status.${step.status}`)}</span></span>
    </button>
  );
}

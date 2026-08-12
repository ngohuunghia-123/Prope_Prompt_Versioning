import { useTranslation } from 'react-i18next';
import type { WorkflowStep } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

export interface WorkflowStepButtonProps { step: WorkflowStep; selected: boolean; current: boolean; onSelect: () => void; }

export function WorkflowStepButton({ step, selected, current, onSelect }: WorkflowStepButtonProps) {
  const { t } = useTranslation();
  return (
    <button type="button" aria-current={current ? 'step' : undefined} aria-pressed={selected} onClick={onSelect} className={cn('ml-6 w-[calc(100%-1.5rem)] cursor-pointer rounded-xl border-l-2 border-transparent px-3 py-2.5 text-left transition-colors duration-(--prope-motion-duration-fast) hover:bg-surface focus-visible:outline-2 focus-visible:outline-focus', selected && 'border-secondary bg-surface shadow-panel', step.status === 'skipped' && 'opacity-70')}>
      <span className="min-w-0"><span className="flex items-center justify-between gap-2"><strong className="block truncate text-body font-semibold text-ink">{t(`lifecycle.workflow.steps.${step.id}.title`)}</strong><span className={cn('text-caption text-muted', current && 'font-medium text-link')}>{t(`lifecycle.workflow.status.${step.status}`)}</span></span><span className="mt-1 block text-caption text-muted">{t(`lifecycle.workflow.steps.${step.id}.description`)}</span></span>
    </button>
  );
}

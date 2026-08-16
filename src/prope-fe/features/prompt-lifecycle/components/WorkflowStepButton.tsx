import { CheckCircle, DotsThree, WarningCircle, CircleDashed } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { WorkflowStep } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

export interface WorkflowStepButtonProps { step: WorkflowStep; selected: boolean; current: boolean; onSelect: () => void; index?: number; }

export function WorkflowStepButton({ step, selected, current, onSelect, index }: WorkflowStepButtonProps) {
  const { t } = useTranslation();
  const statusIcon = {
    passed: <CheckCircle aria-hidden className="size-4 text-success" weight="fill" />,
    running: <CircleDashed aria-hidden className="size-4 animate-spin text-secondary" />,
    warning: <WarningCircle aria-hidden className="size-4 text-warning-text" weight="fill" />,
    failed: <WarningCircle aria-hidden className="size-4 text-danger" weight="fill" />,
    pending: <CircleDashed aria-hidden className="size-4 text-muted/50" />,
    waiting: <DotsThree aria-hidden className="size-4 text-muted/50" weight="bold" />,
    skipped: <CircleDashed aria-hidden className="size-4 text-muted/30" />,
  };
  return (
    <button
      type="button"
      aria-current={current ? 'step' : undefined}
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        'w-full cursor-pointer rounded-xl border border-transparent px-3 py-2.5 text-left transition-all duration-150',
        'hover:bg-surface/80',
        selected && 'border-secondary/30 bg-surface shadow-sm',
        current && 'ring-1 ring-secondary/50',
        step.status === 'skipped' && 'opacity-50'
      )}
    >
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 shrink-0">{statusIcon[step.status]}</div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {index && <span className="text-caption text-muted/60">#{index}</span>}
            <span className={cn('text-body font-medium', selected || current ? 'text-ink' : 'text-muted')}>
              {t(`lifecycle.workflow.steps.${step.id}.title`)}
            </span>
          </div>
          {step.result && (
            <p className={cn('mt-1 text-caption leading-relaxed', step.status === 'warning' ? 'text-warning-text' : 'text-muted')}>
              {step.result}
            </p>
          )}
          {step.status === 'running' && (
            <div className="mt-1 flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-secondary" />
              <span className="text-caption text-secondary">{t('lifecycle.workflow.running')}</span>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

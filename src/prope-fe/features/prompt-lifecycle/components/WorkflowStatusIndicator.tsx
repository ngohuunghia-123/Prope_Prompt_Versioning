import { CheckCircle, Clock, MinusCircle, SpinnerGap, WarningCircle, XCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import type { WorkflowStatus } from '@/features/prompt-lifecycle/types';

const styles: Record<WorkflowStatus, string> = {
  pending: 'border-border bg-subtle text-muted',
  running: 'border-info-strong bg-info text-info-strong',
  passed: 'border-success-strong bg-success text-success-text',
  warning: 'border-warning-strong bg-warning text-warning-strong',
  failed: 'border-danger-strong bg-danger text-danger-text',
  waiting: 'border-warning-strong bg-warning text-warning-strong',
  skipped: 'border-border-disabled bg-disabled text-disabled-text',
};

export interface WorkflowStatusIndicatorProps { status: WorkflowStatus; compact?: boolean; }

export function WorkflowStatusIndicator({ status, compact = false }: WorkflowStatusIndicatorProps) {
  const { t } = useTranslation();
  const Icon = status === 'running' ? SpinnerGap : status === 'passed' ? CheckCircle : status === 'warning' || status === 'waiting' ? WarningCircle : status === 'failed' ? XCircle : status === 'skipped' ? MinusCircle : Clock;
  return <span className={cn('inline-flex w-fit items-center gap-2 rounded-full border px-2.5 py-1.5 text-caption font-medium', styles[status], status === 'skipped' && 'opacity-70')}><Icon aria-hidden weight={status === 'passed' ? 'fill' : 'regular'} className={cn('size-4 shrink-0', status === 'running' && 'animate-spin motion-reduce:animate-none')} />{compact ? <span className="sr-only">{t(`lifecycle.workflow.status.${status}`)}</span> : t(`lifecycle.workflow.status.${status}`)}</span>;
}

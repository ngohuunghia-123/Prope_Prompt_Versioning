import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowClockwise, Check, ClockCounterClockwise, PencilSimple, X } from '@phosphor-icons/react';
import { useState, type ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { hitlReasonSchema, type HitlReasonValues, type WorkflowAction, type WorkflowStep } from '@/features/prompt-lifecycle/types';

type ActionName = WorkflowAction['action'];
const reasonActions: ActionName[] = ['rejectRevise', 'requestChanges', 'rollback'];

function actionsFor(step: WorkflowStep): ActionName[] {
  if (step.id === 'WaitEngineerApproval') return ['approve', 'rejectRevise'];
  if (step.id === 'WaitReviewerApproval') return ['approve', 'retry', 'requestChanges'];
  if (step.id === 'WaitProductionApproval') return ['approve', 'rollback'];
  if (step.id === 'CanaryGate') return ['extend', 'rollback'];
  return [];
}

const icons: Record<ActionName, ReactNode> = {
  approve: <Check aria-hidden />, rejectRevise: <X aria-hidden />, retry: <ArrowClockwise aria-hidden />,
  requestChanges: <PencilSimple aria-hidden />, extend: <ClockCounterClockwise aria-hidden />, rollback: <ClockCounterClockwise aria-hidden />,
};

export interface HitlDecisionPanelProps { step: WorkflowStep; pending: boolean; onAction: (action: ActionName, reason?: string) => void; }

export function HitlDecisionPanel({ step, pending, onAction }: HitlDecisionPanelProps) {
  const { t } = useTranslation();
  const [reasonAction, setReasonAction] = useState<ActionName | null>(null);
  const form = useForm<HitlReasonValues>({ resolver: zodResolver(hitlReasonSchema), defaultValues: { reason: '' } });
  const submitReason = form.handleSubmit(({ reason }) => { if (reasonAction) onAction(reasonAction, reason); });
  const selectAction = (action: ActionName) => reasonActions.includes(action) ? setReasonAction(action) : onAction(action);
  const actions = actionsFor(step);
  return (
    <aside aria-labelledby="hitl-title" className="grid gap-4 rounded-modal border border-warning-strong bg-warning p-5 shadow-floating sm:p-6">
      <div><p className="text-overline font-bold tracking-navigation-overline text-warning-strong uppercase">{t('lifecycle.workflow.hitl.eyebrow')}</p><h3 id="hitl-title" className="mt-2 font-display text-heading-2 text-ink">{t(`lifecycle.workflow.hitl.titles.${step.id}`)}</h3><p className="mt-2 text-body text-muted">{t(`lifecycle.workflow.hitl.summaries.${step.id}`)}</p></div>
      {step.metrics?.length ? <dl className="grid gap-3 sm:grid-cols-3">{step.metrics.map((metric) => <div key={metric.label} className="rounded-lg border border-border bg-surface p-3"><dt className="text-caption text-muted">{metric.label}</dt><dd className="mt-1 text-body-large font-semibold text-ink">{metric.value}</dd></div>)}</dl> : null}
      {step.warning ? <p className="rounded-lg border border-warning-strong bg-surface p-3 text-body text-ink">{step.warning}</p> : null}
      {step.diff ? <div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-border bg-surface p-3"><p className="text-caption font-semibold text-muted">{t('lifecycle.workflow.hitl.before')}</p><pre className="mt-2 whitespace-pre-wrap font-sans text-body text-ink">{step.diff.before}</pre></div><div className="rounded-lg border border-border bg-surface p-3"><p className="text-caption font-semibold text-muted">{t('lifecycle.workflow.hitl.after')}</p><pre className="mt-2 whitespace-pre-wrap font-sans text-body text-ink">{step.diff.after}</pre></div></div> : null}
      <div className="rounded-lg border border-border bg-surface p-3"><p className="text-caption font-semibold text-muted">{t('lifecycle.workflow.hitl.evidence')}</p><p className="mt-2 text-body text-ink">{step.evidence ?? t('lifecycle.workflow.noData')}</p></div>
      {reasonAction ? <form className="grid gap-3" onSubmit={(event) => void submitReason(event)}><Textarea className="min-h-24 bg-surface" label={t('lifecycle.workflow.hitl.reason')} error={form.formState.errors.reason ? t('lifecycle.workflow.hitl.reasonRequired') : undefined} {...form.register('reason')} /><div className="flex flex-wrap gap-2"><Button type="button" intent="neutral" onClick={() => { setReasonAction(null); form.reset(); }}>{t('common.cancel')}</Button><Button type="submit" intent="danger" loading={pending}>{t('lifecycle.workflow.hitl.submitDecision')}</Button></div></form> : <div className="flex flex-wrap gap-2">{actions.map((action) => <Button key={action} type="button" intent={action === 'approve' ? 'success' : action === 'retry' || action === 'extend' ? 'neutral' : 'danger'} disabled={pending} leadingIcon={icons[action]} onClick={() => selectAction(action)}>{t(`lifecycle.workflow.actions.${action}`)}</Button>)}</div>}
    </aside>
  );
}

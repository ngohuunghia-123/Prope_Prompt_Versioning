import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import { HitlDecisionPanel } from '@/features/prompt-lifecycle/components/HitlDecisionPanel';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { WorkflowStepDetail } from '@/features/prompt-lifecycle/components/WorkflowStepDetail';
import { WorkflowStepper } from '@/features/prompt-lifecycle/components/WorkflowStepper';
import { useWorkflowActionMutation, workflowOptions } from '@/features/prompt-lifecycle/queries';
import type { WorkflowAction, WorkflowStepId } from '@/features/prompt-lifecycle/types';

export interface EvaluationWorkflowProps { promptId: string; }

export function EvaluationWorkflow({ promptId }: EvaluationWorkflowProps) {
  const { t } = useTranslation();
  const query = useQuery(workflowOptions(promptId));
  const actionMutation = useWorkflowActionMutation(promptId);
  const [selectedId, setSelectedId] = useState<WorkflowStepId>();
  const currentId = query.data?.currentStepId;
  useEffect(() => { if (currentId) setSelectedId(currentId); }, [currentId]);
  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data.steps.length) return <QueryState state="empty" />;
  const activeSelectedId = selectedId ?? query.data.currentStepId;
  const selectedStep = query.data.steps.find((step) => step.id === activeSelectedId);
  const currentStep = query.data.steps.find((step) => step.id === query.data.currentStepId);
  const onAction = (action: WorkflowAction['action'], reason?: string) => {
    if (!currentStep) return;
    actionMutation.mutate({ promptId, stepId: currentStep.id, action, reason });
  };
  return (
    <section aria-labelledby="evaluation-workflow-title" className="grid gap-5">
      <div><p className="text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t('lifecycle.workflow.eyebrow')}</p><h2 id="evaluation-workflow-title" className="mt-2 font-display text-heading-2 text-ink">{t('lifecycle.workflow.title')}</h2><p className="mt-2 text-body text-muted">{t('lifecycle.workflow.description')}</p></div>
      {actionMutation.isError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{t('lifecycle.workflow.actionError')}</Notification> : null}
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-2"><WorkflowStepper steps={query.data.steps} currentId={query.data.currentStepId} selectedId={activeSelectedId} onSelect={setSelectedId} /></div>
        <div className="grid content-start gap-5 lg:col-span-3">
          {selectedStep ? <div className="rounded-modal border border-border bg-surface p-5 shadow-panel sm:p-6"><WorkflowStepDetail step={selectedStep} /></div> : <QueryState state="empty" />}
          {currentStep?.status === 'waiting' && selectedStep?.id === currentStep.id ? <div className="lg:sticky lg:top-24 lg:self-start"><HitlDecisionPanel step={currentStep} pending={actionMutation.isPending} onAction={onAction} /></div> : null}
        </div>
      </div>
    </section>
  );
}

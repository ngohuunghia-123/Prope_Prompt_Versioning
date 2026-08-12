import type { EvaluationWorkflow, WorkflowAction, WorkflowStatus, WorkflowStepId } from '@/features/prompt-lifecycle/types';

function updateStatuses(workflow: EvaluationWorkflow, updates: Partial<Record<WorkflowStepId, WorkflowStatus>>, currentStepId: WorkflowStepId) {
  return { ...workflow, currentStepId, steps: workflow.steps.map((step) => {
    const nextStatus = updates[step.id];
    return nextStatus === undefined ? step : { ...step, status: nextStatus };
  }) };
}

export function applyWorkflowAction(workflow: EvaluationWorkflow, input: WorkflowAction): EvaluationWorkflow {
  if (input.stepId === 'WaitEngineerApproval' && input.action === 'approve') {
    return updateStatuses(workflow, { WaitEngineerApproval: 'passed', CreateCandidate: 'passed', RunEval: 'passed', CostAnalysis: 'warning', RegressionGate: 'warning', ExplainResults: 'passed', WaitReviewerApproval: 'waiting' }, 'WaitReviewerApproval');
  }
  if (input.stepId === 'WaitEngineerApproval' && input.action === 'rejectRevise') {
    return updateStatuses(workflow, { WaitEngineerApproval: 'failed', OptimizePrompt: 'running' }, 'OptimizePrompt');
  }
  if (input.stepId === 'WaitReviewerApproval' && input.action === 'approve') {
    return updateStatuses(workflow, { WaitReviewerApproval: 'passed', StartCanary: 'passed', ObserveCanary: 'passed', CanaryGate: 'warning', WaitProductionApproval: 'waiting' }, 'WaitProductionApproval');
  }
  if (input.stepId === 'WaitReviewerApproval' && input.action === 'retry') {
    return updateStatuses(workflow, { RunEval: 'running', CostAnalysis: 'pending', RegressionGate: 'pending', WaitReviewerApproval: 'pending' }, 'RunEval');
  }
  if (input.stepId === 'WaitReviewerApproval' && input.action === 'requestChanges') {
    return updateStatuses(workflow, { WaitReviewerApproval: 'failed', OptimizePrompt: 'running' }, 'OptimizePrompt');
  }
  if (input.stepId === 'WaitProductionApproval' && input.action === 'approve') {
    return updateStatuses(workflow, { WaitProductionApproval: 'passed', ValidateBaseline: 'passed', PromoteProduction: 'running', StoreLesson: 'pending' }, 'PromoteProduction');
  }
  if (input.action === 'rollback') return updateStatuses(workflow, { WaitProductionApproval: 'failed', PromoteProduction: 'failed', Rollback: 'passed', StoreLesson: 'running' }, 'StoreLesson');
  if (input.action === 'extend') return updateStatuses(workflow, { ObserveCanary: 'running', CanaryGate: 'pending' }, 'ObserveCanary');
  return workflow;
}

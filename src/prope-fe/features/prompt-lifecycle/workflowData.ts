import { evaluationWorkflowSchema, type EvaluationWorkflow, type WorkflowStep } from '@/features/prompt-lifecycle/types';

const baseSteps: WorkflowStep[] = [
  { id: 'LoadContext', stage: 'prepare', status: 'passed', startedAt: '2026-08-12T08:00:00+07:00', endedAt: '2026-08-12T08:00:04+07:00', durationSeconds: 4, result: 'Workspace context and released revision loaded.', branches: [] },
  { id: 'RetrieveKnowledge', stage: 'prepare', status: 'passed', durationSeconds: 7, result: 'Relevant checkout policies retrieved.', branches: [] },
  { id: 'AnalyzePrompt', stage: 'prepare', status: 'passed', durationSeconds: 11, result: 'Prompt structure and template variables analyzed.', branches: [] },
  { id: 'OptimizePrompt', stage: 'prepare', status: 'passed', durationSeconds: 9, result: 'Candidate preserves the requested output contract.', branches: ['rejectRevise', 'requestChanges'] },
  { id: 'WaitEngineerApproval', stage: 'engineer', status: 'waiting', evidence: 'Template variables and the JSON handoff contract remain unchanged.', diff: { before: 'Follow checkout policy and return a handoff.', after: 'Follow the approved checkout policy and return the required JSON handoff.' }, branches: ['approve', 'rejectRevise'] },
  { id: 'CreateCandidate', stage: 'evaluation', status: 'pending', branches: [] },
  { id: 'RunEval', stage: 'evaluation', status: 'pending', branches: ['retry'] },
  { id: 'CostAnalysis', stage: 'evaluation', status: 'pending', branches: [] },
  { id: 'RegressionGate', stage: 'evaluation', status: 'pending', result: 'PASS_WITH_WARNING', warning: 'Cost delta requires reviewer attention.', branches: ['retry', 'requestChanges'] },
  { id: 'ExplainResults', stage: 'reviewer', status: 'pending', branches: [] },
  { id: 'ExplainFailure', stage: 'reviewer', status: 'skipped', branches: ['retry', 'requestChanges'] },
  { id: 'WaitReviewerApproval', stage: 'reviewer', status: 'pending', evidence: 'Deterministic assertions completed against candidate and released baselines.', warning: 'Candidate cost is higher than the released baseline.', metrics: [{ label: 'Deterministic eval', value: '18/20' }, { label: 'Candidate cost', value: '$0.084' }, { label: 'Released cost', value: '$0.079' }], diff: { before: 'Follow checkout policy and return a handoff.', after: 'Follow the approved checkout policy and return the required JSON handoff.' }, branches: ['approve', 'retry', 'requestChanges'] },
  { id: 'StartCanary', stage: 'canary', status: 'pending', branches: [] },
  { id: 'ObserveCanary', stage: 'canary', status: 'pending', branches: ['extend'] },
  { id: 'CanaryGate', stage: 'canary', status: 'pending', branches: ['extend', 'rollback'] },
  { id: 'WaitProductionApproval', stage: 'canary', status: 'pending', branches: ['approve', 'rollback', 'staleBaseline'] },
  { id: 'Rollback', stage: 'canary', status: 'skipped', branches: [] },
  { id: 'ValidateBaseline', stage: 'canary', status: 'pending', branches: ['staleBaseline'] },
  { id: 'PromoteProduction', stage: 'canary', status: 'pending', branches: ['rollback'] },
  { id: 'StoreLesson', stage: 'canary', status: 'pending', branches: [] },
];

export function createEvaluationWorkflow(promptId: string, running = false): EvaluationWorkflow {
  const steps = baseSteps.map((step) => ({ ...step }));
  if (running) {
    for (const step of steps) step.status = step.id === 'LoadContext' ? 'running' : step.id === 'ExplainFailure' || step.id === 'Rollback' ? 'skipped' : 'pending';
    const loadContext = steps.find((step) => step.id === 'LoadContext');
    if (loadContext) { loadContext.startedAt = new Date().toISOString(); loadContext.endedAt = undefined; loadContext.durationSeconds = undefined; }
    return evaluationWorkflowSchema.parse({ promptId, currentStepId: 'LoadContext', steps });
  }
  return evaluationWorkflowSchema.parse({ promptId, currentStepId: 'WaitEngineerApproval', steps });
}

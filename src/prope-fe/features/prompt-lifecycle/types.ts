import { z } from 'zod';
import { parseXmlBlocks } from '@/features/prompt-lifecycle/xmlBlocks';

export const promptStatusSchema = z.enum(['draft', 'inReview', 'approved', 'inUse', 'retired']);

export const revisionSchema = z.object({
  id: z.string(),
  number: z.string(),
  status: promptStatusSchema,
  author: z.string(),
  createdAt: z.string(),
  summary: z.string(),
  evalPassed: z.number().int().nonnegative(),
  evalTotal: z.number().int().positive(),
  cost: z.number().nonnegative(),
});

export const promptSchema = z.object({
  id: z.string(),
  title: z.string(),
  modelName: z.string(),
  owner: z.string(),
  access: z.enum(['private', 'workspace']),
  status: promptStatusSchema,
  revision: z.string(),
  updatedAt: z.string(),
  tags: z.array(z.string()),
});

export const promptDetailSchema = promptSchema.extend({
  purpose: z.string(),
  provider: z.string(),
  providerModel: z.string(),
  fallbackAnswer: z.string(),
  promptBody: z.string(),
  revisions: z.array(revisionSchema),
});

export const reviewSchema = z.object({
  id: z.string(),
  promptId: z.string(),
  promptTitle: z.string(),
  revision: z.string(),
  owner: z.string(),
  submittedAt: z.string(),
  summary: z.string(),
  passed: z.number().int().nonnegative(),
  total: z.number().int().positive(),
  candidateCost: z.number().nonnegative(),
  releasedCost: z.number().nonnegative(),
});

export const providerSchema = z.object({
  id: z.string(),
  name: z.string(),
  models: z.array(z.string()),
  state: z.enum(['connected', 'attention']),
  updatedAt: z.string(),
});

export const callRecordSchema = z.object({
  id: z.string(),
  promptTitle: z.string(),
  versionId: z.string(),
  consumer: z.string(),
  timestamp: z.string(),
  tokens: z.number().int().nonnegative(),
  cost: z.number().nonnegative(),
  outcome: z.enum(['success', 'fallback', 'error']),
});

export const promptEditorSchema = z.object({
  title: z.string().min(2),
  modelName: z.string().regex(/^[a-z0-9-]+\/[a-z0-9-]+$/),
  access: z.enum(['private', 'workspace']),
  provider: z.string().min(1),
  providerModel: z.string().min(1),
  promptBody: z.string().min(20).refine((value) => parseXmlBlocks(value).success),
  fallbackAnswer: z.string().min(1),
  changeSummary: z.string().min(4),
});

export const providerFormSchema = z.object({
  provider: z.string().min(1),
  credential: z.string().min(8),
  model: z.string().min(1),
});

export const releaseFormSchema = z.object({
  action: z.enum(['normal', 'restore', 'breakGlass']),
  targetRevision: z.string().min(1),
  reason: z.string(),
}).superRefine((value, context) => {
  if (value.action === 'breakGlass' && value.reason.trim().length < 4) {
    context.addIssue({ code: 'custom', path: ['reason'], message: 'reasonRequired' });
  }
});

export const workflowStatusSchema = z.enum(['pending', 'running', 'passed', 'warning', 'failed', 'waiting', 'skipped']);
export const workflowStageSchema = z.enum(['prepare', 'engineer', 'evaluation', 'reviewer', 'canary']);
export const workflowStepIdSchema = z.enum([
  'LoadContext', 'RetrieveKnowledge', 'AnalyzePrompt', 'OptimizePrompt', 'WaitEngineerApproval',
  'CreateCandidate', 'RunEval', 'CostAnalysis', 'RegressionGate', 'ExplainResults', 'ExplainFailure',
  'WaitReviewerApproval', 'StartCanary', 'ObserveCanary', 'CanaryGate', 'WaitProductionApproval',
  'Rollback', 'ValidateBaseline', 'PromoteProduction', 'StoreLesson',
]);
export const workflowBranchSchema = z.enum(['approve', 'rejectRevise', 'retry', 'requestChanges', 'extend', 'staleBaseline', 'rollback']);
export const workflowStepSchema = z.object({
  id: workflowStepIdSchema,
  stage: workflowStageSchema,
  status: workflowStatusSchema,
  startedAt: z.string().optional(),
  endedAt: z.string().optional(),
  durationSeconds: z.number().nonnegative().optional(),
  result: z.string().optional(),
  warning: z.string().optional(),
  evidence: z.string().optional(),
  metrics: z.array(z.object({ label: z.string(), value: z.string() })).optional(),
  diff: z.object({ before: z.string(), after: z.string() }).optional(),
  branches: z.array(workflowBranchSchema).default([]),
});
export const evaluationWorkflowSchema = z.object({
  promptId: z.string(),
  currentStepId: workflowStepIdSchema,
  steps: z.array(workflowStepSchema),
});
export const workflowActionSchema = z.object({
  promptId: z.string(),
  stepId: workflowStepIdSchema,
  action: z.enum(['approve', 'rejectRevise', 'retry', 'requestChanges', 'extend', 'rollback']),
  reason: z.string().optional(),
});
export const hitlReasonSchema = z.object({ reason: z.string().trim().min(4) });

export type Prompt = z.infer<typeof promptSchema>;
export type PromptDetail = z.infer<typeof promptDetailSchema>;
export type Review = z.infer<typeof reviewSchema>;
export type Provider = z.infer<typeof providerSchema>;
export type CallRecord = z.infer<typeof callRecordSchema>;
export type PromptEditorValues = z.infer<typeof promptEditorSchema>;
export type ProviderFormValues = z.infer<typeof providerFormSchema>;
export type ReleaseFormValues = z.infer<typeof releaseFormSchema>;
export type EvaluationWorkflow = z.infer<typeof evaluationWorkflowSchema>;
export type WorkflowStep = z.infer<typeof workflowStepSchema>;
export type WorkflowStepId = z.infer<typeof workflowStepIdSchema>;
export type WorkflowStatus = z.infer<typeof workflowStatusSchema>;
export type WorkflowAction = z.infer<typeof workflowActionSchema>;
export type HitlReasonValues = z.infer<typeof hitlReasonSchema>;

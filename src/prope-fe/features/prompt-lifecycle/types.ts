import { z } from 'zod';
import { parseXmlBlocks } from '@/features/prompt-lifecycle/xmlBlocks';

/**
 * The lifecycle label a screen prints. **Derived, never stored.**
 *
 * The backend keeps three separate facts — the prompt's own `active | retired`,
 * whether a released pointer exists, and the revision's `Draft | In review |
 * Approved` — and no column holds this. `adapters.lifecycleStatus` is the single
 * place the derivation happens; see its docstring for the precedence and for why
 * the registry list is coarser than the detail page.
 */
export const promptStatusSchema = z.enum(['draft', 'inReview', 'approved', 'inUse', 'retired']);
export type LifecycleStatus = z.infer<typeof promptStatusSchema>;

export const revisionSchema = z.object({
  id: z.string(),
  number: z.string(),
  revisionNumber: z.number().int().positive(),
  status: promptStatusSchema,
  author: z.string(),
  createdAt: z.string(),
  summary: z.string(),
  // **Optional, and absent is not zero.** Eval results live on runs, and a run
  // belongs to a revision *and* a suite — there may be none, or several. The
  // review screen carries them for the revision under review; the revision chain
  // does not. A `0/0` here would read as "failed everything" rather than "nobody
  // has asked", so the screens render an em dash instead.
  evalPassed: z.number().int().nonnegative().optional(),
  evalTotal: z.number().int().positive().optional(),
  cost: z.number().nonnegative().optional(),
});

export const promptSchema = z.object({
  id: z.string(),
  title: z.string(),
  modelName: z.string(),
  /** The owner's display name where it could be resolved, and their id where it could not. */
  owner: z.string(),
  ownerId: z.string(),
  access: z.enum(['private', 'workspace']),
  status: promptStatusSchema,
  revision: z.string(),
  releasedVersionId: z.string().nullable(),
  updatedAt: z.string(),
  tags: z.array(z.string()),
  purpose: z.string(),
});

export const promptDetailSchema = promptSchema.extend({
  /** The configured provider's display name, or an empty string when the revision binds none. */
  provider: z.string(),
  providerModel: z.string(),
  fallbackAnswer: z.string(),
  /** Lives on the revision, not on the prompt — a prompt has no body of its own. */
  promptBody: z.string(),
  revisions: z.array(revisionSchema),
});

/**
 * One row of the review queue.
 *
 * Assembled from `GET /review-tasks` plus the prompt each task names. The
 * pass/cost figures come from the review screen and are **per task**, so they are
 * optional here: fetching a review screen for every row would be a fan-out on the
 * queue, and the numbers appear when the reviewer opens the task.
 */
export const reviewSchema = z.object({
  id: z.string(),
  promptId: z.string(),
  versionId: z.string(),
  promptTitle: z.string(),
  revision: z.string(),
  owner: z.string(),
  submittedAt: z.string(),
  summary: z.string(),
  /** `true` when the task is past `due_at`. The queue sorts on it. */
  overdue: z.boolean(),
  status: z.string(),
  passed: z.number().int().nonnegative().optional(),
  total: z.number().int().nonnegative().optional(),
  candidateCost: z.number().nonnegative().optional(),
  releasedCost: z.number().nonnegative().optional(),
});

export const providerSchema = z.object({
  id: z.string(),
  name: z.string(),
  models: z.array(z.string()),
  state: z.enum(['connected', 'attention']),
  verificationStatus: z.string(),
  verificationError: z.string().nullable(),
  /** The only credential-derived value that ever crosses. The secret is unreadable after creation (A-113). */
  credentialLastFour: z.string().nullable(),
  updatedAt: z.string(),
});

export const callRecordSchema = z.object({
  id: z.string(),
  promptTitle: z.string(),
  versionId: z.string(),
  consumer: z.string(),
  timestamp: z.string(),
  tokens: z.number().int().nonnegative(),
  /** A decimal string, never a float (A-107). `costStatus` says whether to believe it. */
  cost: z.string().nullable().optional(),
  costStatus: z.string(),
  currency: z.string().nullable(),
  outcome: z.enum(['success', 'fallback', 'error']),
});

export type Revision = z.infer<typeof revisionSchema>;

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
  // Required by `ProviderCreate`, and validated server-side against ADR-0047's
  // SSRF guard — dispatch connects to the address it validated, so a base URL the
  // form accepted and the server refused is a refusal the form must surface
  // rather than a field it can quietly omit.
  baseUrl: z.string().min(1),
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

import { z } from 'zod';

export const testInputSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(3),
  content: z.string().min(10),
  assertionType: z.enum(['contains', 'regex', 'json']),
  expected: z.string().min(1),
});

export const evaluationMetricSchema = z.object({
  baseline: z.number().nullable(),
  candidate: z.number(),
  delta: z.number().nullable(),
});

export const comparisonResultSchema = z.object({
  inputId: z.string().min(1),
  baselineOutput: z.string().min(1).nullable(),
  candidateOutput: z.string().min(1),
  outcome: z.enum(['pass', 'fail', 'error']),
});

export const evaluationRunSchema = z.object({
  id: z.string().min(1),
  completedAt: z.string(),
  results: z.array(comparisonResultSchema),
  tokens: evaluationMetricSchema,
  cost: evaluationMetricSchema,
  hasCostWarning: z.boolean(),
  requiresAcknowledgement: z.boolean(),
  deltaUnavailableReason: z.enum(['firstRelease', 'incompleteRun']).nullable(),
});

export const evaluationSuiteSummarySchema = z.object({
  id: z.string().min(1), name: z.string().min(1), version: z.number().int().positive(),
  outputModality: z.enum(['text', 'structured']), inputs: z.array(testInputSchema), latestRun: evaluationRunSchema.nullable(),
});

export const evaluationWorkspaceSchema = z.object({
  promptId: z.string().min(1),
  suiteName: z.string().min(1),
  suiteVersion: z.number().int().positive(),
  outputModality: z.enum(['text', 'structured']),
  revisionNumber: z.number().int().positive(),
  revisionSummary: z.string().min(1),
  inputs: z.array(testInputSchema),
  latestRun: evaluationRunSchema.nullable(),
  additionalSuites: z.array(evaluationSuiteSummarySchema),
  warningAccepted: z.boolean(),
  readyForReview: z.boolean(),
});

export const testInputFormSchema = z.object({
  name: z.string().trim().min(3, 'name'),
  content: z.string().trim().min(10, 'content'),
  assertionType: z.enum(['contains', 'regex', 'json']),
  expected: z.string().trim().min(1, 'expected'),
});

export const evaluationSuiteFormSchema = z.object({
  name: z.string().trim().min(2, 'suiteName'),
  outputModality: z.enum(['text', 'structured']),
});

export type EvaluationWorkspace = z.infer<typeof evaluationWorkspaceSchema>;
export type EvaluationRun = z.infer<typeof evaluationRunSchema>;
export type TestInput = z.infer<typeof testInputSchema>;
export type TestInputFormValues = z.infer<typeof testInputFormSchema>;
export type EvaluationSuiteFormValues = z.infer<typeof evaluationSuiteFormSchema>;

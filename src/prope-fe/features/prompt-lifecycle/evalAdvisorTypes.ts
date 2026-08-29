import { z } from 'zod';

/**
 * The evaluation advisor's wire shapes — the two advice routes of the eval
 * module (`POST .../datasets/suggest`, `POST .../eval-runs/analysis`).
 *
 * Kept beside `evalTypes.ts` rather than inside it for the same reason that
 * file stays apart from `types.ts`: these describe `evaluation/advisor.py` and
 * `evaluation/schemas.py`, and a rename on one side should not type-check
 * silently against the other.
 */

export const datasetSuggestionSchema = z.object({
  dataset_id: z.string(),
  name: z.string(),
  /** Why this set, in one sentence a person can judge without opening it. */
  reason: z.string(),
  confidence: z.number().min(0).max(1),
});

export const datasetSuggestSchema = z.object({
  prompt_id: z.string(),
  version_id: z.string(),
  suggestions: z.array(datasetSuggestionSchema).default([]),
});

export const analysisFindingSchema = z.object({
  suite_name: z.string(),
  assertion_type: z.string(),
  failed: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
  issue: z.string(),
  advice: z.string(),
  severity: z.enum(['advice', 'warning']),
});

export const evalAnalysisSchema = z.object({
  prompt_id: z.string(),
  version_id: z.string(),
  runs_considered: z.number().int().nonnegative(),
  brief: z.string(),
  findings: z.array(analysisFindingSchema).default([]),
});

export type DatasetSuggestion = z.infer<typeof datasetSuggestionSchema>;
export type DatasetSuggest = z.infer<typeof datasetSuggestSchema>;
export type AnalysisFinding = z.infer<typeof analysisFindingSchema>;
export type EvalAnalysis = z.infer<typeof evalAnalysisSchema>;

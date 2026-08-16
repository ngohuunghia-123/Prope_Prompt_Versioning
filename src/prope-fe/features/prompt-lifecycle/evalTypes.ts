import { z } from 'zod';

/**
 * The evaluation module's wire shapes, as it actually serves them.
 *
 * Deliberately separate from `types.ts`, which is the mock catalogue's own
 * vocabulary (`Dataset`, `EvalDatasetResult`, `testCaseCount`). Those types
 * describe fixtures; these describe `src/prope/evaluation/schemas.py`. Keeping
 * them apart is what stops a rename on one side from silently type-checking
 * against the other.
 */

export const datasetKindSchema = z.enum(['golden', 'regression', 'red-team']);

export const outputModalitySchema = z.enum(['text', 'structured']);

/**
 * One row of the dataset tree. Builtin and workspace-owned datasets share this
 * shape on purpose — the tree never learns which kind it is rendering, so step
 * 4b's workspace rows arrive without touching this file.
 *
 * `folder` is a slug, and `''` is the *Chung* group: applies workspace-wide,
 * filed under no domain area. Every shipped set sits there.
 */
export const datasetSchema = z.object({
  dataset_id: z.string(),
  name: z.string(),
  description: z.string(),
  kind: datasetKindSchema,
  output_modality: outputModalitySchema,
  case_count: z.number().int().nonnegative(),
  folder: z.string(),
  read_only: z.boolean(),
  /** Why ticking this set may fail a prompt that is working correctly. */
  applicability: z.string().nullable().default(null),
  fingerprint: z.string(),
});

/**
 * A prompt's choice of one dataset.
 *
 * `suite_id` is null until the first run — attaching writes no suite. `stale`
 * says the next run will write a new suite version rather than reuse the last
 * one. `dataset` is null when the id no longer resolves, which happens when a
 * shipped set's version is bumped: the old id retires and the row survives, so
 * the tree renders it as unresolved rather than the page failing.
 */
export const attachmentSchema = z.object({
  dataset_id: z.string(),
  suite_name: z.string(),
  suite_id: z.string().nullable(),
  stale: z.boolean(),
  attached_by: z.string(),
  attached_at: z.string(),
  dataset: datasetSchema.nullable().default(null),
});

export const assertionSchema = z.object({
  type: z.string(),
  value: z.unknown().nullable().default(null),
});

/**
 * One case as the editor loads and saves it.
 *
 * No `case_id`: a dataset edit replaces the case list wholesale rather than
 * reconciling it, so an id would be stable only until the next save. `ordinal`
 * is the identity a case has within its dataset. `input_messages` is the same
 * chat-turn array the runtime dispatches, though the editor only ever writes a
 * single user turn — a multi-turn case is authorable in the shipped catalogue
 * and not yet in the UI.
 */
export const datasetCaseSchema = z.object({
  ordinal: z.number().int(),
  name: z.string(),
  input_messages: z.array(z.record(z.string(), z.unknown())),
  input_variables: z.record(z.string(), z.unknown()).default({}),
  assertions: z.array(assertionSchema).default([]),
});

export const datasetDetailSchema = datasetSchema.extend({
  cases: z.array(datasetCaseSchema).default([]),
});

export const datasetDeletedSchema = z.object({
  dataset_id: z.string(),
  /** How many prompts lost a tick. Reported so a delete is not a surprise. */
  detached: z.number().int().nonnegative(),
});

/** The assertion types the editor offers, in the order it offers them. */
export const EDITABLE_ASSERTION_TYPES = [
  'substring',
  'required_phrase',
  'forbidden_phrase',
  'regex',
  'max_length',
  'exact',
  'json_schema',
  'max_latency',
  'max_cost',
] as const;

export type EditableAssertionType = (typeof EDITABLE_ASSERTION_TYPES)[number];

/**
 * Which assertion types the engine accepts for each modality, mirroring
 * `ASSERTION_TYPES_BY_MODALITY`. Offering one the server will refuse is a
 * validation error somebody meets after typing rather than before.
 */
export const ASSERTION_TYPES_BY_MODALITY: Record<
  'text' | 'structured',
  readonly EditableAssertionType[]
> = {
  text: [
    'substring',
    'required_phrase',
    'forbidden_phrase',
    'regex',
    'max_length',
    'exact',
    'json_schema',
    'max_latency',
    'max_cost',
  ],
  structured: ['json_schema', 'max_latency', 'max_cost'],
};

/** The types whose value is a number rather than a string. */
export const NUMERIC_ASSERTION_TYPES: readonly EditableAssertionType[] = [
  'max_length',
  'max_latency',
  'max_cost',
];

export const runStatusSchema = z.enum([
  'queued',
  'running',
  'completed',
  'interrupted',
  'refused',
]);

export const caseOutcomeSchema = z.enum(['pass', 'fail', 'error']);

export const runRoleSchema = z.enum(['candidate', 'baseline']);

export const evalRunHandleSchema = z.object({
  run_id: z.string(),
  suite_id: z.string(),
  suite_name: z.string(),
  suite_version: z.number().int(),
  role: runRoleSchema,
});

export const evalRunAcceptedSchema = z.object({
  prompt_id: z.string(),
  version_id: z.string(),
  runs: z.array(evalRunHandleSchema),
});

export const evalRunSchema = z.object({
  run_id: z.string(),
  prompt_id: z.string(),
  version_id: z.string(),
  suite_id: z.string(),
  role: runRoleSchema,
  status: runStatusSchema,
  refused_reason: z.string().nullable().default(null),
  started_at: z.string().nullable().default(null),
  finished_at: z.string().nullable().default(null),
  pass_count: z.number().int().nonnegative(),
  fail_count: z.number().int().nonnegative(),
  error_count: z.number().int().nonnegative(),
  input_tokens: z.number().int().nullable().default(null),
  output_tokens: z.number().int().nullable().default(null),
  cost_amount: z.coerce.number().nullable().default(null),
  cost_currency: z.string().nullable().default(null),
});

export const assertionResultSchema = z.object({
  type: z.string(),
  passed: z.boolean(),
  detail: z.string().nullable().default(null),
});

export const caseResultSchema = z.object({
  case_result_id: z.string(),
  run_id: z.string(),
  case_id: z.string(),
  outcome: caseOutcomeSchema,
  assertion_results: z.array(assertionResultSchema),
  output_content: z.string().nullable().default(null),
  latency_ms: z.number().int().nullable().default(null),
  input_tokens: z.number().int().nullable().default(null),
  output_tokens: z.number().int().nullable().default(null),
  error_code: z.string().nullable().default(null),
  attempt_count: z.number().int(),
  created_at: z.string(),
});

export const evalSuiteSchema = z.object({
  suite_id: z.string(),
  prompt_id: z.string(),
  name: z.string(),
  suite_version: z.number().int(),
  output_modality: outputModalitySchema,
  case_count: z.number().int().nonnegative(),
  cases: z
    .array(
      z.object({
        case_id: z.string(),
        ordinal: z.number().int(),
        name: z.string(),
        input_messages: z.array(z.record(z.string(), z.unknown())),
        assertions: z.array(z.object({ type: z.string(), value: z.unknown() })),
      }),
    )
    .nullable()
    .default(null),
});

/** Mirrors `MAX_ATTACHED_DATASETS` — the server refuses past this. */
export const MAX_ATTACHED_DATASETS = 8;

/** Mirrors `MAX_CASES_PER_SUITE`. A dataset cannot hold more. */
export const MAX_CASES_PER_DATASET = 20;

/** The folder slug the server uses for "applies workspace-wide". */
export const SHARED_FOLDER = '';

/** What the editor sends. Mirrors `DatasetWrite`. */
export interface DatasetWriteInput {
  name: string;
  description: string;
  kind: DatasetKind;
  output_modality: 'text' | 'structured';
  folder: string;
  cases: {
    name: string;
    input_messages: { role: string; content: string }[];
    input_variables: Record<string, string>;
    assertions: { type: string; value: unknown }[];
  }[];
  copy_from?: string;
}

export type DatasetKind = z.infer<typeof datasetKindSchema>;
export type EvalDataset = z.infer<typeof datasetSchema>;
export type EvalDatasetDetail = z.infer<typeof datasetDetailSchema>;
export type EvalDatasetCase = z.infer<typeof datasetCaseSchema>;
export type DatasetDeleted = z.infer<typeof datasetDeletedSchema>;
export type DatasetAttachment = z.infer<typeof attachmentSchema>;
export type EvalRunHandle = z.infer<typeof evalRunHandleSchema>;
export type EvalRunAccepted = z.infer<typeof evalRunAcceptedSchema>;
export type EvalRunStatus = z.infer<typeof runStatusSchema>;
export type EvalRunDetail = z.infer<typeof evalRunSchema>;
export type EvalCaseResult = z.infer<typeof caseResultSchema>;
export type EvalCaseOutcome = z.infer<typeof caseOutcomeSchema>;
export type EvalSuiteDetail = z.infer<typeof evalSuiteSchema>;

/** A run and everything the workspace shows about it, assembled client-side. */
export interface EvalSuiteReport {
  handle: EvalRunHandle;
  run: EvalRunDetail | null;
  cases: EvalCaseResult[];
  suite: EvalSuiteDetail | null;
}

export function isTerminal(status: EvalRunStatus): boolean {
  return status === 'completed' || status === 'interrupted' || status === 'refused';
}

import { z } from 'zod';

import { evalRunSchema } from '@/features/prompt-lifecycle/evalTypes';

/**
 * The three reads behind the prompt-detail tabs: Log, Production, Eval.
 *
 * **Snake case, as the API sends it.** The convention this file follows is
 * `evalTypes.ts`'s and not `types.ts`'s: no `.transform()` into camelCase. The
 * mock layer transformed because its fixtures were written camelCase by hand;
 * these shapes are the server's, and a rename in the middle is one more place a
 * field can go missing between the response and the screen.
 *
 * **No request or response body appears anywhere below, and none may.** ADR-0018
 * forbids a read path for `ledger.call_body`, `tests/security/
 * test_no_body_read_path.py` asserts it against the API, and the absence here is
 * the client-side half of the same rule: there is no field for a body to arrive
 * in, so a future endpoint that started sending one would have nowhere to put it.
 */

export const callSourceSchema = z.enum(['gateway', 'eval', 'playground']);
export const callOutcomeSchema = z.enum([
  'ok',
  'fallback',
  'truncated',
  'caller_error',
  'upstream_error',
]);
export const usageWindowSchema = z.enum(['24h', '7d', '30d']);

export type CallSource = z.infer<typeof callSourceSchema>;
export type CallOutcome = z.infer<typeof callOutcomeSchema>;
export type UsageWindow = z.infer<typeof usageWindowSchema>;

/**
 * `cost_status` says whether to believe `cost`.
 *
 * `unpriced` means no price row covered this call — the tokens were spent and
 * nobody can say what they were worth yet. Rendering that as `0` would
 * under-report, so every surface reading this must branch on the status rather
 * than on `cost === null`.
 */
export const costStatusSchema = z.enum(['priced', 'unpriced', 'not_applicable']);

export const callRecordSchema = z.object({
  call_id: z.string(),
  source: callSourceSchema,
  version_id: z.string().nullable().default(null),
  revision_number: z.number().int().nullable().default(null),
  /** Which integration called, never who. A key, not a person. */
  consumer_key_id: z.string().nullable().default(null),
  /**
   * That key's name, resolved server-side. Null means one of two things and the
   * client tells them apart by `consumer_key_id`: null id is the internal
   * caller; a non-null id with no label is a key whose row has gone, and the id
   * is what to show.
   */
  consumer_label: z.string().nullable().default(null),
  provider_config_id: z.string().nullable().default(null),
  upstream_model: z.string().nullable().default(null),
  outcome: callOutcomeSchema,
  pinned: z.boolean(),
  fallback: z.boolean(),
  streaming: z.boolean(),
  input_tokens: z.number().int().nullable().default(null),
  output_tokens: z.number().int().nullable().default(null),
  usage_status: z.enum(['reported', 'unknown']),
  /**
   * `coerce` because money crosses as a string: it is `Numeric(20, 10)` in the
   * database and a JSON number would round it through a double. Safe to hold as
   * a number here only because nothing in the client **sums** these — the totals
   * come from the server, which adds them as decimals.
   */
  cost: z.coerce.number().nullable().default(null),
  currency: z.string().nullable().default(null),
  cost_status: costStatusSchema,
  added_latency_ms: z.number().int().nullable().default(null),
  upstream_duration_ms: z.number().int().nullable().default(null),
  error_class: z.string().nullable().default(null),
  created_at: z.string(),
});

export const usageCostSchema = z.object({
  currency: z.string(),
  amount: z.coerce.number(),
});

export const usageBucketSchema = z.object({
  consumer_key_id: z.string().nullable().default(null),
  /**
   * The key's name. Null for the internal caller, and also for a key whose row
   * has gone — the client falls back to the id in the second case and to its own
   * internal label in the first.
   */
  label: z.string().nullable().default(null),
  requests: z.number().int().nonnegative(),
  input_tokens: z.number().int().nonnegative(),
  output_tokens: z.number().int().nonnegative(),
  /** One entry per currency. Two providers, two totals, and never a sum. */
  cost: z.array(usageCostSchema),
  unpriced_count: z.number().int().nonnegative(),
  error_count: z.number().int().nonnegative(),
  fallback_count: z.number().int().nonnegative(),
  last_called_at: z.string().nullable().default(null),
});

export const promptUsageSchema = z.object({
  prompt_id: z.string(),
  window: usageWindowSchema,
  since: z.string(),
  source: callSourceSchema.nullable().default(null),
  total_requests: z.number().int().nonnegative(),
  buckets: z.array(usageBucketSchema),
});

/**
 * A run plus what it ran. `.extend` rather than a fresh object, so the run's own
 * fields keep one definition shared with `GET /eval-runs/{run_id}`.
 */
export const evalRunSummarySchema = evalRunSchema.extend({
  suite_name: z.string().nullable().default(null),
  suite_version: z.number().int().nullable().default(null),
  dataset_id: z.string().nullable().default(null),
  dataset_name: z.string().nullable().default(null),
});

export type CallRecord = z.infer<typeof callRecordSchema>;
export type UsageCost = z.infer<typeof usageCostSchema>;
export type UsageBucket = z.infer<typeof usageBucketSchema>;
export type PromptUsage = z.infer<typeof promptUsageSchema>;
export type EvalRunSummary = z.infer<typeof evalRunSummarySchema>;

/** A run that finished and therefore has counts worth reading. */
export function isSettled(run: EvalRunSummary): boolean {
  return run.status === 'completed';
}

/** Cases the run actually reached a verdict on. Zero for a refused run. */
export function caseTotal(run: EvalRunSummary): number {
  return run.pass_count + run.fail_count + run.error_count;
}

/**
 * Pass rate, or null when there is nothing to divide by.
 *
 * Null and not zero: a run that never executed a case has no pass rate, and
 * showing it as 0% would read as *everything failed* — the opposite of what a
 * refusal means.
 */
export function passRate(run: EvalRunSummary): number | null {
  const total = caseTotal(run);
  return total === 0 ? null : run.pass_count / total;
}

/**
 * What to write in an "app" cell, given the two nulls mean different things.
 *
 * `internalLabel` is passed in rather than imported so this file stays free of
 * anything that renders — it is the schema module, and the label is a value the
 * workspace feature owns.
 */
export function appLabel(
  row: { consumer_key_id: string | null; consumer_label?: string | null },
  internalLabel: string,
): string {
  if (row.consumer_key_id === null) return internalLabel;
  return row.consumer_label ?? row.consumer_key_id;
}

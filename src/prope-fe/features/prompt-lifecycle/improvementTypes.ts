import { z } from 'zod';

/**
 * The findings inbox and the evidence card, as the API sends it. INT-045..INT-050.
 *
 * **Snake case, no `.transform()`.** `insightsTypes.ts`'s convention rather than
 * `types.ts`'s: these shapes are the server's, and a rename in the middle is one
 * more place a field can go missing between the response and the screen.
 *
 * **There is no `message` field anywhere below, and there must not be one.**
 * ADR-0053: the client renders the `code`, keyed by `detector_id`, with `params`
 * interpolated — *"{share} câu trả lời bị cắt ngang, trước đó là {prior_share}"*
 * lives in `improvement.vi.ts` and the numbers come from here. A `message` field
 * would be a second, untranslated rendering path, and the one that got used would
 * be whichever a developer reached for first.
 *
 * The single exception is `evidence_line`, which the server generates directly in
 * Vietnamese and has already run through its redaction rail **before storing it**
 * (SR-9). It renders as plain text and never as markdown or HTML — the rail
 * strips links and tags, and the renderer being unable to follow one is the
 * second half of that guarantee.
 *
 * **There is no `rationale` field, and its absence is ADR-0068 §4.** The card
 * carries what changed and the eval delta per case; it does not carry the model's
 * story about why its own edit works, because that story does not describe the
 * edit's behaviour and showing it asks a reviewer to trust an unreliable
 * narrative on top of an unvalidated judgement.
 */

/** Two members. There is no `blocker`, and ADR-0067 §4 is why — inherited whole. */
export const severitySchema = z.enum(['advice', 'warning']);

/**
 * The closed detector catalogue. **Every member needs a `vi` key or CI fails**
 * (AC-11), which is the same contract `readinessTypes` carries.
 *
 * Enumerated rather than left as `z.string()` on purpose, and the cost is
 * understood: `apiClient` uses `schema.parse`, so a detector the server knows and
 * this file does not takes down the whole inbox rather than one row. That is the
 * right failure — a row rendering as a blank line in a queue somebody is meant to
 * act on is worse, because it is silent. The fix on both sides is the same edit.
 */
export const detectorIdSchema = z.enum([
  'truncation_rising',
  'fallback_rising',
  'caller_error_clustering',
  'output_ratio_drift',
  'usage_unknown_appearing',
  'cost_unpriced_appearing',
  'latency_tail_shift',
  'pinned_share_rising',
  'chain_depth_rising',
  'released_but_unused',
  'profile_drift',
  'probe_leak_appeared',
]);

export const remedyKindSchema = z.enum(['note', 'case', 'edit']);

/** Three, and growing costs a migration — `ck_improvement_proposal_remedy_family_values`. */
export const remedyFamilySchema = z.enum([
  'tighten_refusal_block',
  'add_length_rule',
  'add_brevity_clause',
]);

/**
 * One case, both sides. The card renders these rather than a verdict, because
 * *"passed the gate"* read as an endorsement is exactly how the gate stops being
 * a floor and starts being a rubber stamp.
 */
export const gateCaseSchema = z.object({
  case_id: z.string(),
  name: z.string(),
  baseline: z.string().nullable(),
  candidate: z.string(),
});

export const gateDeltaSchema = z.object({
  suite_id: z.string(),
  suite_name: z.string(),
  case_count: z.number(),
  baseline_run_id: z.string().nullable(),
  baseline_pass: z.number(),
  candidate_pass: z.number(),
  candidate_error: z.number(),
  cases: z.array(gateCaseSchema),
});

export const proposalSchema = z.object({
  proposal_id: z.string(),
  remedy_kind: remedyKindSchema,
  remedy_family: remedyFamilySchema.nullable(),
  /** Absent on `note` and `case`: neither proposes a body, so neither was gated. */
  gate_delta: gateDeltaSchema.nullable(),
  expires_at: z.string(),
});

export const findingSchema = z.object({
  finding_id: z.string(),
  prompt_id: z.string(),
  detector_id: detectorIdSchema,
  severity: severitySchema,
  /** The detector's own figures. Interpolated into the `vi` sentence for its code. */
  params: z.record(z.string(), z.unknown()),
  /** The one triage sentence, or absent when the model was down. */
  evidence_line: z.string().nullable(),
  first_seen: z.string(),
  last_seen: z.string(),
  /** **Fourteen occurrences, not fourteen rows.** The dedupe index is why. */
  occurrence_count: z.number(),
  status: z.string(),
  proposal: proposalSchema.nullable(),
});

/**
 * The inbox. **A prompt the reader cannot see contributes nothing** — no row, no
 * count, no total that differs (SR-7). `total` is computed after authorisation
 * for exactly that reason, so a workspace where everything is invisible answers
 * byte-identically to one where nothing is wrong.
 */
export const inboxSchema = z.object({
  findings: z.array(findingSchema),
  total: z.number(),
  warning_count: z.number(),
  advice_count: z.number(),
});

/**
 * What accept returns. **No revision was written** (SR-6): this is the body for a
 * prefilled editor, and the write is registry's `create_revision` on a separate,
 * explicit request the person makes themselves.
 */
export const proposalAcceptedSchema = z.object({
  proposal_id: z.string(),
  prompt_id: z.string(),
  remedy_family: remedyFamilySchema.nullable(),
  candidate_body: z.string().nullable(),
  gate_delta: gateDeltaSchema.nullable(),
});

export const scheduleSchema = z.object({
  enabled: z.boolean(),
  cadence_days: z.number(),
  namespaces: z.array(z.string()),
  prompt_ids: z.array(z.string()),
  last_run_at: z.string().nullable(),
  updated_at: z.string(),
});

export type Severity = z.infer<typeof severitySchema>;
export type DetectorId = z.infer<typeof detectorIdSchema>;
export type RemedyKind = z.infer<typeof remedyKindSchema>;
export type RemedyFamily = z.infer<typeof remedyFamilySchema>;
export type GateCase = z.infer<typeof gateCaseSchema>;
export type GateDelta = z.infer<typeof gateDeltaSchema>;
export type ImprovementProposal = z.infer<typeof proposalSchema>;
export type ImprovementFinding = z.infer<typeof findingSchema>;
export type ImprovementInbox = z.infer<typeof inboxSchema>;
export type ProposalAccepted = z.infer<typeof proposalAcceptedSchema>;
export type ImprovementSchedule = z.infer<typeof scheduleSchema>;

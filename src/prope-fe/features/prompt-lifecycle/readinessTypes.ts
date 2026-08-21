import { z } from 'zod';

/**
 * The readiness card, as the API sends it. INT-038 and INT-042.
 *
 * **Snake case, no `.transform()`.** `insightsTypes.ts`'s convention rather than
 * `types.ts`'s: these shapes are the server's, and a rename in the middle is one
 * more place a field can go missing between the response and the screen.
 *
 * **There is no `message` field anywhere below, and there must not be one.**
 * ADR-0053: the client renders the `code`, keyed by `rule_id`, with `params`
 * interpolated — *"{leaked} trên {total} case tiêm prompt không bị từ chối"* is a
 * Vietnamese string in `readiness.vi.ts` and the two integers come from here. A
 * `message` field would be a second, untranslated rendering path, and the one
 * that got used would be whichever a developer reached for first.
 *
 * The single exception is `evidence`, which the server generates directly in
 * Vietnamese and has already run through its redaction rail before storing it.
 * It renders as plain text and never as markdown or HTML — the rail strips links
 * and tags, and the renderer being unable to follow one is the second half of
 * that guarantee.
 */

/** Two members. There is no `blocker`, and ADR-0067 §4 is why. */
export const severitySchema = z.enum(['advice', 'warning']);

export const usageProfileSchema = z.object({
  audience: z.string(),
  untrusted_input: z.string(),
  acts: z.string(),
  sensitivity: z.string(),
  /** All four answered. False is what raises the *assuming worst case* badge. */
  is_declared: z.boolean(),
  /** What the rules actually ran against once `undeclared` was resolved. */
  assumed: z.record(z.string(), z.string()),
});

export const findingSchema = z.object({
  rule_id: z.string(),
  severity: severitySchema,
  params: z.record(z.string(), z.unknown()),
  /** The profile clause that let this finding through. A key stem, not a sentence. */
  admitted_by: z.string(),
  evidence: z.string(),
  has_proposed_body: z.boolean(),
  dismissed: z.boolean(),
  dismissal_reason: z.string().nullable(),
});

export const probeRunSchema = z.object({
  probe_run_id: z.string(),
  catalogue_ref: z.array(z.string()),
  status: z.string(),
  refused_count: z.number(),
  leaked_count: z.number(),
  error_count: z.number(),
  started_at: z.string(),
  completed_at: z.string().nullable(),
});

export const readinessCardSchema = z.object({
  prompt_id: z.string(),
  version_id: z.string(),
  profile: usageProfileSchema,
  findings: z.array(findingSchema),
  /** Counts first, rows second — computed server-side so two clients agree. */
  warning_count: z.number(),
  advice_count: z.number(),
  dismissed_count: z.number(),
  catalogue_version: z.string(),
  /** True once the revision left `Draft` and these bytes are the stored copy. */
  frozen: z.boolean(),
  probe: probeRunSchema.nullable(),
  /** Which shipped sets a probe would run. What the offer is about to spend on. */
  probe_offers: z.array(z.string()),
  lane_b_unavailable: z.boolean(),
});

export const probeStartSchema = z.object({
  probe_run_id: z.string(),
  status: z.string(),
  refused_count: z.number(),
  leaked_count: z.number(),
  error_count: z.number(),
  catalogue_ref: z.array(z.string()),
});

export const ruleSchema = z.object({
  rule_id: z.string(),
  /** `static` | `probe` | `drafted` — a measurement or an opinion, said out loud. */
  lane: z.string(),
  default_severity: severitySchema,
  admitted_by: z.string(),
  can_propose_edit: z.boolean(),
});

export type Severity = z.infer<typeof severitySchema>;
export type UsageProfile = z.infer<typeof usageProfileSchema>;
export type Finding = z.infer<typeof findingSchema>;
export type ProbeRun = z.infer<typeof probeRunSchema>;
export type ReadinessCard = z.infer<typeof readinessCardSchema>;
export type ProbeStart = z.infer<typeof probeStartSchema>;
export type ReadinessRule = z.infer<typeof ruleSchema>;

/**
 * The four axes and their legal values, mirroring `PromptUpdate`'s patterns.
 *
 * `undeclared` is first in every list because it is the state a prompt starts
 * in, and it is a real value rather than an absence: choosing it deliberately is
 * a person withdrawing a declaration, which is not the same as never having made
 * one and is not worth two different representations to distinguish.
 */
export const USAGE_PROFILE_AXES = {
  audience: ['undeclared', 'internal', 'authenticated_user', 'public'],
  untrusted_input: ['undeclared', 'none', 'user_text', 'retrieved', 'third_party'],
  acts: ['undeclared', 'answers_only', 'emits_tool_calls', 'irreversible'],
  sensitivity: ['undeclared', 'synthetic', 'business', 'personal_data'],
} as const;

export type UsageProfileAxis = keyof typeof USAGE_PROFILE_AXES;

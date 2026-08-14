import { z } from 'zod';

/**
 * The API's own shapes, spelled as the API spells them.
 *
 * This file is snake_case on purpose and is the only place in the SPA that is.
 * Every schema here mirrors a pydantic model under `src/prope/<module>/schemas.py`
 * field for field, and `types.ts` holds the camelCase view models the components
 * read.
 * Keeping the two apart is what makes a backend rename a change to one adapter
 * rather than a change to nine components.
 *
 * **Nothing here is `.strict()`.** Zod strips unknown keys by default, and that is
 * the behaviour to want: the API may add a field before the SPA knows what to do
 * with it, and a client that refused the response would turn an additive backend
 * change into an outage.
 *
 * **Money is a string on the wire and stays a string here.** Costs are
 * `Numeric(20, 10)` in the database (A-107), and `z.number()` would round them
 * through a double on the way in — quietly, and in the direction of looking
 * cheaper. Formatting happens at the point of display.
 */

/** `registry.prompt_property.status` — the shelf, not the revision. Retired is terminal (A-049). */
export const wirePromptStatusSchema = z.enum(['active', 'retired']);

/** `registry.revision.status`, spaces and capitals included (A-065). Stored exactly like this. */
export const wireRevisionStatusSchema = z.enum(['Draft', 'In review', 'Approved']);

export const wireAccessLevelSchema = z.enum(['private', 'workspace']);

export const wirePromptSchema = z.object({
  prompt_id: z.string(),
  model_name: z.string(),
  namespace: z.string(),
  name: z.string(),
  title: z.string(),
  purpose: z.string(),
  owner_id: z.string(),
  access_level: wireAccessLevelSchema,
  status: wirePromptStatusSchema,
  tags: z.array(z.string()),
  released_version_id: z.string().nullable().optional(),
  released_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const wirePromptSearchResultSchema = z.object({
  prompt_id: z.string(),
  title: z.string(),
  purpose: z.string(),
  similarity: z.number().nullable().optional(),
  keywords: z.array(z.string()),
  topics: z.array(z.string()),
  entities: z.array(z.string()),
  variations: z.record(z.string(), z.array(z.string())),
  language: z.array(z.string()),
  matched_fields: z.array(z.string()),
  is_indexed: z.boolean(),
});

export const wirePromptSearchResponseSchema = z.object({
  prompts: z.array(wirePromptSearchResultSchema),
  next_cursor: z.string().nullable().optional(),
  total: z.number().nullable().optional(),
  search_type: z.enum(['quick', 'ai']),
});

export const wirePromptIndexStatusSchema = z.object({
  is_indexed: z.boolean(),
  is_stale: z.boolean().default(false),
  indexed_at: z.string().nullable().optional(),
  indexed_by: z.string().nullable().optional(),
  version_id: z.string().nullable().optional(),
  nearest_neighbor: z.object({
    prompt_id: z.string(),
    title: z.string().optional(),
    similarity: z.number().nullable().optional(),
  }).nullable().optional(),
});

export const wirePromptIndexPreviewSchema = z.object({
  keywords: z.array(z.string()),
  topics: z.array(z.string()),
  entities: z.array(z.string()),
  variations: z.record(z.string(), z.array(z.string())),
  language: z.array(z.string()),
  duplicate_warning: z.object({
    prompt_id: z.string(),
    title: z.string(),
    similarity: z.number(),
  }).nullable().optional(),
});

export const wirePromptIndexJobSchema = z.object({
  job_id: z.string(),
  status: z.enum(['pending', 'running', 'completed', 'failed']),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
});

export const wireRevisionSummarySchema = z.object({
  version_id: z.string(),
  prompt_id: z.string(),
  revision_number: z.number().int(),
  change_summary: z.string(),
  author_id: z.string(),
  status: wireRevisionStatusSchema,
  provider_config_id: z.string().nullable().optional(),
  upstream_model: z.string().nullable().optional(),
  created_at: z.string(),
});

export const wireRevisionSchema = wireRevisionSummarySchema.extend({
  body: z.string(),
  parameters: z.record(z.string(), z.unknown()),
  fallback_answer: z.string().nullable().optional(),
});

export const wireProviderSchema = z.object({
  provider_config_id: z.string(),
  display_name: z.string(),
  adapter: z.string(),
  base_url: z.string(),
  status: z.string(),
  verification_status: z.string(),
  last_verified_at: z.string().nullable().optional(),
  verification_error: z.string().nullable().optional(),
  // The only credential-derived value that ever crosses the seam. A-113 makes the
  // secret itself unreadable after creation, from any API.
  credential_last_four: z.string().nullable().optional(),
  interactive_concurrency: z.number().int(),
  batch_concurrency: z.number().int(),
  created_by: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const wireModelSchema = z.object({
  model_id: z.string(),
  display_name: z.string().nullable().optional(),
  supports_streaming: z.boolean(),
  available: z.boolean(),
  source: z.string(),
});

export const wireReviewTaskSchema = z.object({
  review_task_id: z.string(),
  prompt_id: z.string(),
  version_id: z.string(),
  kind: z.string(),
  assigned_role: z.string(),
  due_at: z.string().nullable(),
  status: z.string(),
  created_from_release_id: z.string().nullable(),
  created_at: z.string(),
  closed_by: z.string().nullable(),
  closed_at: z.string().nullable(),
  closed_note: z.string().nullable(),
  overdue: z.boolean(),
});

const wireCostDeltaSchema = z.object({
  currency: z.string().nullable().optional(),
  baseline: z.string().nullable().optional(),
  candidate: z.string().nullable().optional(),
  absolute: z.string().nullable().optional(),
  relative: z.string().nullable().optional(),
}).loose();

export const wireSuiteEvidenceSchema = z.object({
  suite_id: z.string(),
  suite_name: z.string(),
  suite_version: z.number().int(),
  run_id: z.string(),
  status: z.string(),
  pass_count: z.number().int(),
  fail_count: z.number().int(),
  error_count: z.number().int(),
  case_count: z.number().int(),
  baseline_run_id: z.string().nullable(),
  baseline_ran_at: z.string().nullable(),
  cost_delta: wireCostDeltaSchema.nullable(),
});

export const wireSummarySchema = z.object({
  suites: z.array(wireSuiteEvidenceSchema),
  total_cost_delta: wireCostDeltaSchema.nullable(),
  // ADR-0005. A failing suite does not block approval; it requires the approver to
  // write down why they are approving anyway, and that reason is recorded.
  requires_acknowledgement: z.boolean(),
  cost_warning: z.boolean(),
});

const wireDiffLineSchema = z.object({
  op: z.string(),
  text: z.string(),
  from_line: z.number().int().nullable(),
  to_line: z.number().int().nullable(),
});

const wireDiffFieldSchema = z.object({
  field: z.string(),
  before: z.string().nullable(),
  after: z.string().nullable(),
  changed: z.boolean(),
});

export const wireDiffSchema = z.object({
  from_version_id: z.string(),
  to_version_id: z.string(),
  lines: z.array(wireDiffLineSchema),
  fields: z.array(wireDiffFieldSchema),
});

export const wireApprovalSchema = z.object({
  approval_id: z.string(),
  prompt_id: z.string(),
  version_id: z.string(),
  decision: z.string(),
  reviewer_id: z.string(),
  comment: z.string().nullable(),
  acknowledgement_reason: z.string().nullable(),
  evidence_digest: z.record(z.string(), z.unknown()),
  // Recorded, never refused — one of the four non-negotiables. The review screen
  // shows it; nothing blocks on it.
  self_approved: z.boolean(),
  decided_at: z.string(),
});

export const wireReviewScreenSchema = z.object({
  prompt_id: z.string(),
  model_name: z.string(),
  revision: z.object({
    version_id: z.string(),
    prompt_id: z.string(),
    revision_number: z.number().int(),
    change_summary: z.string(),
    author_id: z.string(),
    status: z.string(),
    created_at: z.string(),
  }),
  diff: wireDiffSchema.nullable(),
  diff_against_version_id: z.string().nullable(),
  summary: wireSummarySchema.nullable(),
  summary_available: z.boolean(),
  acknowledgement_required: z.boolean(),
  self_authored: z.boolean(),
  released_version_id: z.string().nullable(),
  latest_revision_number: z.number().int(),
  revisions_since: z.number().int(),
  approvals: z.array(wireApprovalSchema),
  review_task: wireReviewTaskSchema.nullable(),
  history: z.array(z.object({
    event_id: z.string(),
    action: z.string(),
    target_type: z.string(),
    target_id: z.string(),
    actor_id: z.string().nullable(),
    reason: z.string().nullable(),
    details: z.record(z.string(), z.unknown()),
    occurred_at: z.string(),
  })),
});

export const wireReleaseSchema = z.object({
  release_id: z.string(),
  prompt_id: z.string(),
  version_id: z.string().nullable(),
  kind: z.string(),
  previous_version_id: z.string().nullable(),
  approval_id: z.string().nullable(),
  break_glass: z.boolean(),
  reason: z.string().nullable(),
  released_by: z.string(),
  released_at: z.string(),
});

/** ADR-0055. Metadata only — there is no body field here because there is no body endpoint. */
export const wireCallRecordSchema = z.object({
  call_id: z.string(),
  source: z.string(),
  version_id: z.string().nullable().optional(),
  revision_number: z.number().int().nullable().optional(),
  consumer_key_id: z.string().nullable().optional(),
  provider_config_id: z.string().nullable().optional(),
  upstream_model: z.string().nullable().optional(),
  outcome: z.string(),
  pinned: z.boolean(),
  fallback: z.boolean(),
  streaming: z.boolean(),
  input_tokens: z.number().int().nullable().optional(),
  output_tokens: z.number().int().nullable().optional(),
  usage_status: z.string(),
  cost: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
  cost_status: z.string(),
  added_latency_ms: z.number().int().nullable().optional(),
  upstream_duration_ms: z.number().int().nullable().optional(),
  error_class: z.string().nullable().optional(),
  created_at: z.string(),
});

export const wireMemberSchema = z.object({
  user_id: z.string(),
  email: z.string().nullable(),
  display_name: z.string().nullable(),
  status: z.string(),
  added_at: z.string(),
  roles: z.array(z.string()),
});

export const wireMemberPageSchema = z.object({
  items: z.array(wireMemberSchema),
  next_cursor: z.string().nullable().optional(),
});

export type WirePrompt = z.infer<typeof wirePromptSchema>;
export type WirePromptSearchResult = z.infer<typeof wirePromptSearchResultSchema>;
export type WireRevision = z.infer<typeof wireRevisionSchema>;
export type WireRevisionSummary = z.infer<typeof wireRevisionSummarySchema>;
export type WireProvider = z.infer<typeof wireProviderSchema>;
export type WireModel = z.infer<typeof wireModelSchema>;
export type WireReviewTask = z.infer<typeof wireReviewTaskSchema>;
export type WireReviewScreen = z.infer<typeof wireReviewScreenSchema>;
export type WireRelease = z.infer<typeof wireReleaseSchema>;
export type WireCallRecord = z.infer<typeof wireCallRecordSchema>;
export type WireSummary = z.infer<typeof wireSummarySchema>;

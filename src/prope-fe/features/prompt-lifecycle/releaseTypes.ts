import { z } from 'zod';

/**
 * The release-control wire shapes, snake_case as the API returns them.
 *
 * **These mirror `src/prope/release_control/schemas.py` field for field.** The
 * module's own vocabulary is kept rather than translated into the front end's
 * camelCase prompt types, because a release is an audit record: `break_glass`,
 * `approval_id` and `evidence_digest` are the names the history rows carry, and
 * a reader comparing this screen against the activity log should see one word
 * for one thing.
 */

/** `Decision` — the two a reviewer may record. There is no "rejected". */
export const decisionSchema = z.enum(['approved', 'changes_requested']);

/** `ReleaseKind`. `withdraw` is its own route and its own permission. */
export const releaseKindSchema = z.enum(['release', 'restore', 'withdraw']);

export const reviewTaskKindSchema = z.enum(['review', 'break_glass_followup']);

export const reviewTaskStatusSchema = z.enum(['open', 'closed', 'superseded']);

/**
 * `RevisionStatus`, stored with spaces and capitals (A-065).
 *
 * `In use` and `Retired` are deliberately absent: the first is derived from the
 * released pointer and the second is a prompt status, so neither is ever stored
 * on a revision. BR-03's foreign key compares `Approved` literally.
 */
export const revisionStatusSchema = z.enum(['Draft', 'In review', 'Approved']);

export const approvalSchema = z.object({
  approval_id: z.string(),
  prompt_id: z.string(),
  version_id: z.string(),
  decision: decisionSchema,
  reviewer_id: z.string(),
  comment: z.string().nullable(),
  acknowledgement_reason: z.string().nullable(),
  evidence_digest: z.record(z.string(), z.unknown()),
  self_approved: z.boolean(),
  decided_at: z.string(),
});

export const releaseSchema = z.object({
  release_id: z.string(),
  prompt_id: z.string(),
  // Null on a withdrawal: nothing is pointed at afterwards.
  version_id: z.string().nullable(),
  kind: releaseKindSchema,
  previous_version_id: z.string().nullable(),
  approval_id: z.string().nullable(),
  break_glass: z.boolean(),
  reason: z.string().nullable(),
  released_by: z.string(),
  released_at: z.string(),
});

export const reviewTaskSchema = z.object({
  review_task_id: z.string(),
  prompt_id: z.string(),
  version_id: z.string(),
  kind: reviewTaskKindSchema,
  assigned_role: z.string(),
  due_at: z.string().nullable(),
  status: reviewTaskStatusSchema,
  created_from_release_id: z.string().nullable(),
  created_at: z.string(),
  closed_by: z.string().nullable(),
  closed_at: z.string().nullable(),
  closed_note: z.string().nullable(),
  overdue: z.boolean(),
});

export const suiteEvidenceSchema = z.object({
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
  cost_delta: z.record(z.string(), z.unknown()).nullable(),
});

export const reviewSummarySchema = z.object({
  suites: z.array(suiteEvidenceSchema),
  total_cost_delta: z.record(z.string(), z.unknown()).nullable(),
  requires_acknowledgement: z.boolean(),
  cost_warning: z.boolean(),
});

export const revisionCardSchema = z.object({
  version_id: z.string(),
  prompt_id: z.string(),
  revision_number: z.number().int(),
  change_summary: z.string(),
  author_id: z.string(),
  status: z.string(),
  created_at: z.string(),
});

export const releaseHistoryEntrySchema = z.object({
  event_id: z.string(),
  action: z.string(),
  target_type: z.string(),
  target_id: z.string(),
  actor_id: z.string().nullable(),
  reason: z.string().nullable(),
  details: z.record(z.string(), z.unknown()),
  occurred_at: z.string(),
});

export const reviewScreenSchema = z.object({
  prompt_id: z.string(),
  model_name: z.string(),
  revision: revisionCardSchema,
  diff: z
    .object({
      from_version_id: z.string(),
      to_version_id: z.string(),
      lines: z.array(
        z.object({
          op: z.string(),
          text: z.string(),
          from_line: z.number().int().nullable(),
          to_line: z.number().int().nullable(),
        }),
      ),
      fields: z.array(
        z.object({
          field: z.string(),
          before: z.string().nullable(),
          after: z.string().nullable(),
          changed: z.boolean(),
        }),
      ),
    })
    .nullable(),
  diff_against_version_id: z.string().nullable(),
  summary: reviewSummarySchema.nullable(),
  summary_available: z.boolean(),
  acknowledgement_required: z.boolean(),
  self_authored: z.boolean(),
  released_version_id: z.string().nullable(),
  latest_revision_number: z.number().int(),
  revisions_since: z.number().int(),
  approvals: z.array(approvalSchema),
  review_task: reviewTaskSchema.nullable(),
  history: z.array(releaseHistoryEntrySchema),
});

export type Approval = z.infer<typeof approvalSchema>;
export type Decision = z.infer<typeof decisionSchema>;
export type Release = z.infer<typeof releaseSchema>;
export type ReleaseKind = z.infer<typeof releaseKindSchema>;
export type ReviewScreen = z.infer<typeof reviewScreenSchema>;
export type ReviewSummary = z.infer<typeof reviewSummarySchema>;
export type ReviewTask = z.infer<typeof reviewTaskSchema>;
export type RevisionStatus = z.infer<typeof revisionStatusSchema>;
export type SuiteEvidence = z.infer<typeof suiteEvidenceSchema>;

/**
 * Which single act is available on this revision right now.
 *
 * The three writing steps are held by three different roles — Owner submits,
 * Reviewer approves, Admin releases — so this is a description of the revision,
 * never of the reader. `unavailable` covers the case the screen still has to
 * render: a revision that is not the newest and is not the released one.
 */
export type ReleaseStep =
  | 'submit'
  | 'awaitingApproval'
  | 'approved'
  | 'released'
  | 'changesRequested'
  | 'unavailable';

/**
 * BR-03, read off the revision rather than guessed from the prompt's status.
 *
 * `Approved` is the only status a release may point at, and the check that
 * matters is the database's — this only decides which button to draw.
 */
export function releaseStep(screen: ReviewScreen): ReleaseStep {
  const status = screen.revision.status;
  const released = screen.released_version_id === screen.revision.version_id;

  if (released) return 'released';
  if (status === 'Approved') return 'approved';
  if (status === 'In review') return 'awaitingApproval';
  if (status === 'Draft') {
    // A draft that already carries a `changes_requested` decision is a draft the
    // reviewer sent back, which is a different sentence to the reader even though
    // the stored status is identical.
    const latest = screen.approvals.at(0);
    if (latest?.decision === 'changes_requested') return 'changesRequested';
    return 'submit';
  }
  return 'unavailable';
}

/** The reviewer's own words, newest first, for the decision trail. */
export function latestApproval(screen: ReviewScreen): Approval | undefined {
  return screen.approvals.at(0);
}

/** Total cases across every suite in the evidence, for the one-line summary. */
export function evidenceTotals(summary: ReviewSummary | null) {
  if (!summary || summary.suites.length === 0) return null;
  return summary.suites.reduce(
    (totals, suite) => ({
      passed: totals.passed + suite.pass_count,
      failed: totals.failed + suite.fail_count,
      errored: totals.errored + suite.error_count,
      cases: totals.cases + suite.case_count,
    }),
    { passed: 0, failed: 0, errored: 0, cases: 0 },
  );
}

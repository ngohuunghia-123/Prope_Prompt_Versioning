import { z } from 'zod';

import { apiRequest } from '@/lib/apiClient';
import {
  approvalSchema,
  releaseSchema,
  reviewScreenSchema,
  reviewTaskSchema,
  type Approval,
  type Release,
  type ReviewScreen,
  type ReviewTask,
} from '@/features/prompt-lifecycle/releaseTypes';

/**
 * The four acts that move a revision to production, and the read behind them.
 *
 * **No mock arm.** The screen this serves replaced a form that called
 * `releaseRevision`, which waited 440 ms and echoed its own input back — so the
 * button said "released" and nothing was. A release is the one act in Prope that
 * a recorded human approval is required for; a convincing fake of it is worse
 * than no button at all.
 *
 * **These are three permissions, not one.** `revision.submit` belongs to the
 * Owner, `revision.approve` to the Reviewer, and `release.create` to the Admin —
 * the seeded matrix gives no role two of them (NFR-01). A 403 from any call here
 * is the normal answer for a reader holding one of the other two roles, and the
 * screen renders it as such rather than as a failure.
 */

const prompts = (promptId: string) => `/api/v1/prompts/${encodeURIComponent(promptId)}`;

const revision = (promptId: string, versionId: string) =>
  `${prompts(promptId)}/revisions/${encodeURIComponent(versionId)}`;

const body = (payload: unknown) => JSON.stringify(payload);

/**
 * Everything the decision needs: the revision, its diff, its eval evidence, the
 * approvals recorded against it, and what is released right now.
 */
export async function getReviewScreen(
  promptId: string,
  versionId: string,
): Promise<ReviewScreen> {
  return apiRequest(`${revision(promptId, versionId)}/review`, { schema: reviewScreenSchema });
}

/** Newest first. A withdrawal appears here as a row with a null `version_id`. */
export async function getReleases(promptId: string, limit = 20): Promise<Release[]> {
  return apiRequest(`${prompts(promptId)}/releases?limit=${limit}`, {
    schema: z.array(releaseSchema),
  });
}

/** Owner's step: `Draft` → `In review`, and the review task that comes with it. */
export async function submitRevision(
  promptId: string,
  versionId: string,
): Promise<ReviewTask> {
  return apiRequest(`${revision(promptId, versionId)}/submit`, {
    method: 'POST',
    schema: reviewTaskSchema,
  });
}

export interface ApproveInput {
  comment?: string | null;
  /**
   * Required when the eval evidence is missing or stale. The server decides
   * whether it is needed and refuses with `release_acknowledgement_required`;
   * the screen asks only after being told.
   */
  acknowledgementReason?: string | null;
}

/** Reviewer's step: `In review` → `Approved`. Self-approval is recorded, not refused. */
export async function approveRevision(
  promptId: string,
  versionId: string,
  input: ApproveInput = {},
): Promise<Approval> {
  return apiRequest(`${revision(promptId, versionId)}/approve`, {
    method: 'POST',
    body: body({
      comment: input.comment ?? null,
      acknowledgement_reason: input.acknowledgementReason ?? null,
    }),
    schema: approvalSchema,
  });
}

/** The other half of the reviewer's step, back to `Draft`. The comment is required. */
export async function requestChanges(
  promptId: string,
  versionId: string,
  comment: string,
): Promise<Approval> {
  return apiRequest(`${revision(promptId, versionId)}/request-changes`, {
    method: 'POST',
    body: body({ comment }),
    schema: approvalSchema,
  });
}

export interface ReleaseInput {
  versionId: string;
  /** `restore` for a revision that was released before; the server checks that. */
  kind?: 'release' | 'restore';
  /**
   * The released pointer the caller believes is current, `null` for "nothing is
   * released". Sent on every call: it is what turns two admins releasing at once
   * into a `release_pointer_conflict` instead of a silent overwrite.
   */
  expectedCurrentVersionId?: string | null;
  reason?: string | null;
}

/** Admin's step. Refused unless the revision is `Approved` — by a database constraint. */
export async function createRelease(promptId: string, input: ReleaseInput): Promise<Release> {
  return apiRequest(`${prompts(promptId)}/releases`, {
    method: 'POST',
    body: body({
      version_id: input.versionId,
      kind: input.kind ?? 'release',
      expected_current_version_id: input.expectedCurrentVersionId ?? null,
      reason: input.reason ?? null,
    }),
    schema: releaseSchema,
  });
}

/**
 * Unpublish. The prompt stops resolving at the gateway and no revision replaces
 * it, which is why this is its own route, its own permission and a required
 * reason.
 */
export async function withdrawRelease(promptId: string, reason: string): Promise<Release> {
  return apiRequest(`${prompts(promptId)}/releases/withdraw`, {
    method: 'POST',
    body: body({ reason }),
    schema: releaseSchema,
  });
}

export interface BreakGlassInput {
  versionId: string;
  reason: string;
  expectedCurrentVersionId?: string | null;
}

/**
 * The declared exception: release without an approval.
 *
 * It is counted, it writes a 24-hour follow-up review task, and that follow-up is
 * what keeps it exceptional. Kept behind a separate confirmation in the UI for
 * the same reason it is a separate permission.
 */
export async function breakGlassRelease(
  promptId: string,
  input: BreakGlassInput,
): Promise<Release> {
  return apiRequest(`${prompts(promptId)}/releases/break-glass`, {
    method: 'POST',
    body: body({
      version_id: input.versionId,
      reason: input.reason,
      expected_current_version_id: input.expectedCurrentVersionId ?? null,
    }),
    schema: releaseSchema,
  });
}

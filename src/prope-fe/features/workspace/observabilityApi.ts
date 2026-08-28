import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';

/**
 * The workspace's opt-in to reading retained request and response content.
 *
 * **This flag is the whole reason the Log & Trace request panel could show
 * nothing.** ADR-0060 puts two conditions on showing somebody a redacted body —
 * the workspace has opted in, and the reader holds Owner, Admin or Reviewer —
 * and a workspace with no retention row has never opted in. Both routes have
 * existed since the ledger shipped; what did not exist was any way to reach
 * them, so every workspace sat on the default and the panel read `disabled`
 * forever.
 *
 * **No mock arm**, on `membersApi`'s rule: this is a privacy control, and a
 * faked one would report content access enabled on a workspace where it is off.
 */
export const contentAccessSchema = z.object({
  workspace_id: z.string(),
  enabled: z.boolean(),
  updated_at: z.string().nullable().optional(),
});

export type ContentAccess = z.infer<typeof contentAccessSchema>;

function route(workspaceId: string): string {
  return `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/observability-content-access`;
}

export async function getContentAccess(workspaceId: string): Promise<ContentAccess> {
  return apiRequest(route(workspaceId), { schema: contentAccessSchema });
}

export async function setContentAccess(workspaceId: string, enabled: boolean): Promise<ContentAccess> {
  return apiRequest(route(workspaceId), {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
    schema: contentAccessSchema,
  });
}

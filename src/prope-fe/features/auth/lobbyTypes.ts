import { z } from 'zod';

/**
 * The lobby's wire types: what a person can see and do while belonging nowhere.
 *
 * **A session may name no workspace** (ADR-0056), and these three shapes are
 * everything that state can reach: the list of workspaces the person is in or
 * waiting on, the code they can redeem to join another, and the workspace they
 * create if they would rather start one.
 *
 * **`status` stays literal.** `active` and `pending` are values the API compares
 * and the client translates at the point of display (ADR-0053 rule 9) — no code
 * anywhere compares a translated label.
 */

const apiRoleSchema = z.enum(['Owner', 'Reviewer', 'Viewer', 'Admin']);

export const membershipStatusSchema = z.enum(['active', 'pending']);
export type MembershipStatus = z.infer<typeof membershipStatusSchema>;

export const workspaceMembershipSchema = z
  .object({
    workspace_id: z.string(),
    name: z.string(),
    slug: z.string(),
    status: membershipStatusSchema,
    roles: z.array(apiRoleSchema),
    added_at: z.string(),
  })
  .transform((membership) => ({
    workspaceId: membership.workspace_id,
    name: membership.name,
    slug: membership.slug,
    status: membership.status,
    roles: membership.roles,
    addedAt: membership.added_at,
  }));

export type WorkspaceMembership = z.infer<typeof workspaceMembershipSchema>;

export const workspaceMembershipListSchema = z
  .object({
    items: z.array(workspaceMembershipSchema),
    current_workspace_id: z.string().nullable(),
  })
  .transform((list) => ({
    items: list.items,
    currentWorkspaceId: list.current_workspace_id,
  }));

export type WorkspaceMembershipList = z.infer<typeof workspaceMembershipListSchema>;

export const createdWorkspaceSchema = z
  .object({
    workspace_id: z.string(),
    name: z.string(),
    slug: z.string(),
    created_at: z.string(),
  })
  .transform((workspace) => ({
    workspaceId: workspace.workspace_id,
    name: workspace.name,
    slug: workspace.slug,
    createdAt: workspace.created_at,
  }));

export type CreatedWorkspace = z.infer<typeof createdWorkspaceSchema>;

/**
 * What redeeming a code answers.
 *
 * `pending` means the request is in a queue an Admin has to act on; `active`
 * means the person was already a member, which is what re-presenting a code they
 * have already used returns. Both are successes — a reload must not read as a
 * failure.
 */
export const redeemedInviteSchema = z
  .object({
    workspace_id: z.string(),
    workspace_name: z.string(),
    status: membershipStatusSchema,
  })
  .transform((redeemed) => ({
    workspaceId: redeemed.workspace_id,
    workspaceName: redeemed.workspace_name,
    status: redeemed.status,
  }));

export type RedeemedInvite = z.infer<typeof redeemedInviteSchema>;

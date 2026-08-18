import { z } from 'zod';

/**
 * Members and invitations, as `access_control` returns them.
 *
 * **`status` and `role` stay literal** (ADR-0053 rule 9). `pending`, `active`,
 * `removed`, `Admin`, `Owner` are values: stored as written, transmitted as
 * written, translated only where they are displayed. Nothing here compares a
 * translated label.
 *
 * **`code` exists on exactly one shape**, for `keyTypes.ts`'s reason: the
 * plaintext appears in the creation response and nowhere else, because only its
 * SHA-256 is stored. Two schemas rather than one optional field, so no component
 * can try to render a code from a list.
 */

export const roleSchema = z.enum(['Owner', 'Reviewer', 'Viewer', 'Admin']);
export type WorkspaceRole = z.infer<typeof roleSchema>;

/** Every role an Admin can hand out, in the order the forms present them. */
export const ASSIGNABLE_ROLES: readonly WorkspaceRole[] = ['Admin', 'Owner', 'Reviewer', 'Viewer'];

export const memberStatusSchema = z.enum(['active', 'pending', 'removed']);
export type MemberStatus = z.infer<typeof memberStatusSchema>;

export const memberSchema = z
  .object({
    user_id: z.string(),
    // Null for a tombstoned account: the columns are NULL and no surface may
    // resolve them to a name (AC-15). The client renders the absence.
    email: z.string().nullable().optional(),
    display_name: z.string().nullable().optional(),
    status: memberStatusSchema,
    roles: z.array(roleSchema),
    added_at: z.string(),
  })
  .transform((member) => ({
    userId: member.user_id,
    email: member.email ?? null,
    displayName: member.display_name ?? null,
    status: member.status,
    roles: member.roles,
    addedAt: member.added_at,
  }));

export type Member = z.infer<typeof memberSchema>;

export const memberPageSchema = z
  .object({
    items: z.array(memberSchema),
    next_cursor: z.string().nullable().optional(),
  })
  .transform((page) => ({ items: page.items, nextCursor: page.next_cursor ?? null }));

export type MemberPage = z.infer<typeof memberPageSchema>;

export const memberRoleSetSchema = z
  .object({ roles: z.array(roleSchema) })
  .transform((set) => ({ roles: set.roles }));

/** `live`, `revoked`, `expired`, `exhausted` — derived by the server, never stored. */
export const inviteStatusSchema = z.enum(['live', 'revoked', 'expired', 'exhausted']);
export type InviteStatus = z.infer<typeof inviteStatusSchema>;

export const inviteSchema = z
  .object({
    invite_id: z.string(),
    invited_email: z.string().nullable().optional(),
    roles: z.array(roleSchema),
    status: inviteStatusSchema,
    created_by: z.string(),
    created_at: z.string(),
    expires_at: z.string(),
    revoked_at: z.string().nullable().optional(),
    max_uses: z.number().nullable().optional(),
    use_count: z.number(),
  })
  .transform((invite) => ({
    inviteId: invite.invite_id,
    invitedEmail: invite.invited_email ?? null,
    roles: invite.roles,
    status: invite.status,
    createdBy: invite.created_by,
    createdAt: invite.created_at,
    expiresAt: invite.expires_at,
    revokedAt: invite.revoked_at ?? null,
    maxUses: invite.max_uses ?? null,
    useCount: invite.use_count,
  }));

export type Invite = z.infer<typeof inviteSchema>;

export const createdInviteSchema = z
  .object({
    invite_id: z.string(),
    code: z.string().nullable().optional(),
    invited_email: z.string().nullable().optional(),
    roles: z.array(roleSchema),
    created_at: z.string(),
    expires_at: z.string(),
    max_uses: z.number().nullable().optional(),
  })
  .transform((invite) => ({
    inviteId: invite.invite_id,
    code: invite.code ?? null,
    invitedEmail: invite.invited_email ?? null,
    roles: invite.roles,
    createdAt: invite.created_at,
    expiresAt: invite.expires_at,
    maxUses: invite.max_uses ?? null,
  }));

export type CreatedInvite = z.infer<typeof createdInviteSchema>;

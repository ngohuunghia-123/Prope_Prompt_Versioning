import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import {
  createdInviteSchema,
  inviteSchema,
  memberPageSchema,
  memberRoleSetSchema,
  type CreatedInvite,
  type Invite,
  type MemberPage,
  type MemberStatus,
  type WorkspaceRole,
} from '@/features/workspace/memberTypes';

/**
 * The member and invitation routes, called for real.
 *
 * **No mock arm** (`keysApi.ts`'s rule). Every write on this screen changes who
 * can reach a workspace, and a faked one would show somebody approved who is
 * still waiting — which is the one thing this feature exists to be certain
 * about.
 */

const dataMode =
  import.meta.env.VITE_DATA_MODE ??
  import.meta.env.VITE_AUTH_MODE ??
  (import.meta.env.DEV ? 'mock' : 'api');
const useRealApi = dataMode === 'api';

export class MembersUnavailable extends Error {
  constructor() {
    super('Member administration needs the real API — start the stack or set VITE_DATA_MODE=api');
    this.name = 'MembersUnavailable';
  }
}

export function membersAreLive(): boolean {
  return useRealApi;
}

function requireRealApi(): void {
  if (!useRealApi) throw new MembersUnavailable();
}

function members(workspaceId: string): string {
  return `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`;
}

function invites(workspaceId: string): string {
  return `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/invites`;
}

export async function listMembers(workspaceId: string, status: MemberStatus | 'all'): Promise<MemberPage> {
  requireRealApi();
  return apiRequest(`${members(workspaceId)}?status=${encodeURIComponent(status)}`, {
    schema: memberPageSchema,
  });
}

/**
 * Replace a member's whole role set.
 *
 * A `PUT` of the set rather than a patch of one role, because with a partial
 * update *"I did not mention Admin"* and *"I want Admin removed"* would be the
 * same request. The server refuses anything that would leave the workspace with
 * zero Admins, which is a `409` the caller shows rather than prevents.
 */
export async function setMemberRoles(
  workspaceId: string,
  userId: string,
  roles: WorkspaceRole[],
): Promise<WorkspaceRole[]> {
  requireRealApi();
  const set = await apiRequest(`${members(workspaceId)}/${encodeURIComponent(userId)}/roles`, {
    method: 'PUT',
    body: JSON.stringify({ roles }),
    schema: memberRoleSetSchema,
  });
  return set.roles;
}

export async function removeMember(workspaceId: string, userId: string): Promise<void> {
  requireRealApi();
  await apiRequest(`${members(workspaceId)}/${encodeURIComponent(userId)}`, { method: 'DELETE' });
}

/** The human gate. The roles are the approver's choice, not the invitation's. */
export async function approveMember(
  workspaceId: string,
  userId: string,
  roles: WorkspaceRole[],
): Promise<WorkspaceRole[]> {
  requireRealApi();
  const set = await apiRequest(`${members(workspaceId)}/${encodeURIComponent(userId)}/approve`, {
    method: 'POST',
    body: JSON.stringify({ roles }),
    schema: memberRoleSetSchema,
  });
  return set.roles;
}

export async function rejectMember(workspaceId: string, userId: string): Promise<void> {
  requireRealApi();
  await apiRequest(`${members(workspaceId)}/${encodeURIComponent(userId)}/reject`, {
    method: 'POST',
  });
}

export async function listInvites(workspaceId: string): Promise<Invite[]> {
  requireRealApi();
  return apiRequest(invites(workspaceId), { schema: z.array(inviteSchema) });
}

/**
 * Create an invitation. **The response is the only time a code exists** — show it
 * once and do not persist it.
 *
 * With an `email` this reserves a seat for one person and grants `roles` the
 * moment that address signs in or registers, whether or not they have an account
 * yet. Without one it mints a code, which grants nothing: whoever redeems it
 * lands in the pending queue and an Admin approves them.
 */
export async function createInvite(
  workspaceId: string,
  input: { email?: string; roles: WorkspaceRole[]; maxUses?: number | null },
): Promise<CreatedInvite> {
  requireRealApi();
  return apiRequest(invites(workspaceId), {
    method: 'POST',
    body: JSON.stringify({
      ...(input.email ? { email: input.email } : {}),
      roles: input.roles,
      ...(input.maxUses ? { max_uses: input.maxUses } : {}),
    }),
    schema: createdInviteSchema,
  });
}

/** Close an invitation early. The row survives with a `revoked_at`. */
export async function revokeInvite(workspaceId: string, inviteId: string): Promise<void> {
  requireRealApi();
  await apiRequest(`${invites(workspaceId)}/${encodeURIComponent(inviteId)}`, { method: 'DELETE' });
}

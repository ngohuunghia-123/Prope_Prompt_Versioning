import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  approveMember,
  createInvite,
  listInvites,
  listMembers,
  rejectMember,
  removeMember,
  revokeInvite,
  setMemberRoles,
} from '@/features/workspace/membersApi';
import type {
  CreatedInvite,
  Invite,
  MemberPage,
  MemberStatus,
  WorkspaceRole,
} from '@/features/workspace/memberTypes';

export const memberQueryKeys = {
  members: (workspaceId: string, status: MemberStatus | 'all') =>
    ['workspace', workspaceId, 'members', status] as const,
  allMembers: (workspaceId: string) => ['workspace', workspaceId, 'members'] as const,
  invites: (workspaceId: string) => ['workspace', workspaceId, 'invites'] as const,
};

export function workspaceMembersOptions(workspaceId: string, status: MemberStatus | 'all') {
  return queryOptions({
    queryKey: memberQueryKeys.members(workspaceId, status),
    queryFn: () => listMembers(workspaceId, status),
    enabled: workspaceId !== '',
    // Shorter than the key list's five minutes, and for the same reason the
    // chooser refetches: the pending queue fills because *somebody else* acted,
    // and an Admin sitting on this screen is waiting for exactly that.
    staleTime: 30 * 1000,
  });
}

export function workspaceInvitesOptions(workspaceId: string) {
  return queryOptions({
    queryKey: memberQueryKeys.invites(workspaceId),
    queryFn: () => listInvites(workspaceId),
    enabled: workspaceId !== '',
    // An invitation lives for one hour, so its derived status changes on the
    // clock rather than on an action. Half a minute keeps `live` from lingering
    // on a row that has expired while the tab was open.
    staleTime: 30 * 1000,
  });
}

/**
 * Every member write invalidates **both** lists.
 *
 * Approving moves a row from `pending` to `active`, so a mutation that
 * invalidated only the list it was fired from would leave the other tab showing
 * the person in the state they just left. The key prefix covers every status
 * filter at once, which is why `allMembers` exists beside `members`.
 */
function useMemberMutationInvalidation(workspaceId: string) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: memberQueryKeys.allMembers(workspaceId) });
    void queryClient.invalidateQueries({ queryKey: memberQueryKeys.invites(workspaceId) });
  };
}

export function useApproveMemberMutation(workspaceId: string) {
  const invalidate = useMemberMutationInvalidation(workspaceId);
  return useMutation<WorkspaceRole[], Error, { userId: string; roles: WorkspaceRole[] }>({
    mutationFn: ({ userId, roles }) => approveMember(workspaceId, userId, roles),
    onSuccess: invalidate,
  });
}

export function useRejectMemberMutation(workspaceId: string) {
  const invalidate = useMemberMutationInvalidation(workspaceId);
  return useMutation<void, Error, string>({
    mutationFn: (userId) => rejectMember(workspaceId, userId),
    onSuccess: invalidate,
  });
}

export function useSetMemberRolesMutation(workspaceId: string) {
  const invalidate = useMemberMutationInvalidation(workspaceId);
  return useMutation<WorkspaceRole[], Error, { userId: string; roles: WorkspaceRole[] }>({
    mutationFn: ({ userId, roles }) => setMemberRoles(workspaceId, userId, roles),
    onSuccess: invalidate,
  });
}

export function useRemoveMemberMutation(workspaceId: string) {
  const invalidate = useMemberMutationInvalidation(workspaceId);
  return useMutation<void, Error, string>({
    mutationFn: (userId) => removeMember(workspaceId, userId),
    onSuccess: invalidate,
  });
}

/**
 * Creating an invitation returns the code, and it is deliberately **not** written
 * into the query cache — only the refetched list is. React Query's cache is a
 * long-lived in-memory store that devtools print and a future `persistQueryClient`
 * would write to disk; the caller keeps the code in component state, shows it
 * once, and loses it on unmount.
 */
export function useCreateInviteMutation(workspaceId: string) {
  const invalidate = useMemberMutationInvalidation(workspaceId);
  return useMutation<
    CreatedInvite,
    Error,
    { email?: string; roles: WorkspaceRole[]; maxUses?: number | null }
  >({
    mutationFn: (input) => createInvite(workspaceId, input),
    onSuccess: invalidate,
  });
}

export function useRevokeInviteMutation(workspaceId: string) {
  const invalidate = useMemberMutationInvalidation(workspaceId);
  return useMutation<void, Error, string>({
    mutationFn: (inviteId) => revokeInvite(workspaceId, inviteId),
    onSuccess: invalidate,
  });
}

export type { Invite, MemberPage };

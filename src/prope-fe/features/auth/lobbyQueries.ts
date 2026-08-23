import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createWorkspace,
  enterWorkspace,
  listMyWorkspaces,
  redeemInvite,
} from '@/features/auth/lobbyApi';
import { authKeys } from '@/features/auth/queries';
import type { CreatedWorkspace, RedeemedInvite } from '@/features/auth/lobbyTypes';
import type { Session } from '@/features/auth/types';

export const lobbyKeys = { workspaces: ['auth', 'workspaces'] as const };

/**
 * The chooser's list.
 *
 * `staleTime: 0` and a refetch on focus, unlike every other list in the SPA: the
 * rows change because **somebody else** acted — an Admin approving a pending
 * request — and the person sitting on this screen is waiting for exactly that.
 * A five-minute cache here would mean staring at `pending` after being let in.
 */
export const myWorkspacesOptions = queryOptions({
  queryKey: lobbyKeys.workspaces,
  queryFn: listMyWorkspaces,
  staleTime: 0,
});

/**
 * Entering replaces the session wholesale.
 *
 * The server issued a **new** session row with a new cookie, so patching
 * `workspaceId` into the cached one would leave the client holding a session id
 * that no longer exists. Everything else is cleared too: every cached query was
 * read under the old tenant, and a stale prompt list from another workspace is
 * the one thing tenant isolation must never look like it allows.
 */
export function useEnterWorkspaceMutation() {
  const queryClient = useQueryClient();
  return useMutation<Session, Error, string>({
    mutationFn: enterWorkspace,
    onSuccess: (session) => {
      queryClient.clear();
      queryClient.setQueryData(authKeys.session, session);
    },
  });
}

export function useCreateWorkspaceMutation() {
  const queryClient = useQueryClient();
  return useMutation<CreatedWorkspace, Error, string>({
    mutationFn: createWorkspace,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: lobbyKeys.workspaces });
    },
  });
}

export function useRedeemInviteMutation() {
  const queryClient = useQueryClient();
  return useMutation<RedeemedInvite, Error, string>({
    mutationFn: redeemInvite,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: lobbyKeys.workspaces });
    },
  });
}

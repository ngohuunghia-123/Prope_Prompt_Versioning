import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { createKey, listKeys, revokeKey, setKeyScope } from '@/features/workspace/keysApi';
import type { ApiKey, CreatedApiKey } from '@/features/workspace/keyTypes';

export const keyQueryKeys = {
  all: (workspaceId: string) => ['workspace', workspaceId, 'keys'] as const,
};

export function workspaceKeysOptions(workspaceId: string) {
  return queryOptions({
    queryKey: keyQueryKeys.all(workspaceId),
    queryFn: () => listKeys(workspaceId),
    enabled: workspaceId !== '',
    // A key list changes only when somebody on this screen changes it, and every
    // mutation below invalidates. Refetching it on every window focus would be a
    // request per tab switch for a table that has not moved.
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Minting returns the plaintext, and it is deliberately **not** written into the
 * query cache — only the refetched list is. React Query's cache is a long-lived
 * in-memory store that devtools print and that a future `persistQueryClient`
 * would write to localStorage; a secret in it is a secret one configuration
 * change away from disk. The caller keeps it in component state, shows it once,
 * and loses it on unmount, which is the intended lifetime.
 */
export function useCreateKeyMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<CreatedApiKey, Error, { name: string; scopeModelNames: string[] }>({
    mutationFn: (input) => createKey(workspaceId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keyQueryKeys.all(workspaceId) });
    },
  });
}

export function useSetKeyScopeMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<ApiKey, Error, { keyId: string; scopeModelNames: string[] }>({
    mutationFn: ({ keyId, scopeModelNames }) => setKeyScope(workspaceId, keyId, scopeModelNames),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keyQueryKeys.all(workspaceId) });
    },
  });
}

export function useRevokeKeyMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (keyId) => revokeKey(workspaceId, keyId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keyQueryKeys.all(workspaceId) });
    },
  });
}

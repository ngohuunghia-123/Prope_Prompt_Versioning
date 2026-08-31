import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { getContentAccess, setContentAccess } from '@/features/workspace/observabilityApi';

export const observabilityQueryKeys = {
  contentAccess: (workspaceId: string) => ['workspace', workspaceId, 'content-access'] as const,
};

export function contentAccessOptions(workspaceId: string) {
  return queryOptions({
    queryKey: observabilityQueryKeys.contentAccess(workspaceId),
    queryFn: () => getContentAccess(workspaceId),
    enabled: workspaceId !== '',
    // A policy flag, changed by hand on this screen and nowhere else. There is
    // no clock and no other actor to race, so it refetches on the write rather
    // than on an interval.
    staleTime: 5 * 60 * 1000,
  });
}

export function useSetContentAccessMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => setContentAccess(workspaceId, enabled),
    onSuccess: (state) => {
      // The response is the new state, so it is written straight in rather than
      // invalidated: the checkbox reads from this query, and a refetch round
      // trip would let it snap back to the old value for a frame.
      queryClient.setQueryData(observabilityQueryKeys.contentAccess(workspaceId), state);
    },
  });
}

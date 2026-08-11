import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSession, login, logout } from '@/features/auth/api';

export const authKeys = { session: ['auth', 'session'] as const };

export const sessionOptions = queryOptions({
  queryKey: authKeys.session,
  queryFn: getSession,
  staleTime: Infinity,
});

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    onSuccess: (session) => queryClient.setQueryData(authKeys.session, session),
  });
}

export function useLogoutMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.setQueryData(authKeys.session, null),
  });
}

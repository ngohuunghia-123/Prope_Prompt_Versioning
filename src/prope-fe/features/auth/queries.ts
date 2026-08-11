import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { changePassword, getSession, login, logout, signup } from '@/features/auth/api';
import type { Session } from '@/features/auth/types';

export const authKeys = { session: ['auth', 'session'] as const };

export const sessionOptions = queryOptions({
  queryKey: authKeys.session,
  queryFn: getSession,
  staleTime: 5 * 60 * 1000,
});

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    onSuccess: (session) => queryClient.setQueryData(authKeys.session, session),
  });
}

export function useSignupMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signup,
    onSuccess: (session) => queryClient.setQueryData(authKeys.session, session),
  });
}

export function useLogoutMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.clear(),
  });
}

export function useChangePasswordMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: changePassword,
    onSuccess: () => queryClient.setQueryData<Session | null>(authKeys.session, (session) => (
      session ? { ...session, mustChangePassword: false } : session
    )),
  });
}

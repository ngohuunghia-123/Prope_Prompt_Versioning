import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateProfile } from '@/features/account/profileApi';
import { authKeys } from '@/features/auth/queries';
import type { Session } from '@/features/auth/types';

export function useUpdateProfileMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (profile) => queryClient.setQueryData<Session | null>(authKeys.session, (session) => (
      session ? { ...session, user: { ...session.user, ...profile } } : session
    )),
  });
}

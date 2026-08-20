import { z } from 'zod';

export const profileUpdateSchema = z.object({
  displayName: z.string().trim().min(2).max(120),
  email: z.email(),
});

export type ProfileUpdateInput = z.infer<typeof profileUpdateSchema>;

/** TanStack boundary ready to be replaced by PATCH /api/v1/auth/profile. */
export async function updateProfile(input: ProfileUpdateInput): Promise<ProfileUpdateInput> {
  await new Promise((resolve) => window.setTimeout(resolve, 350));
  return profileUpdateSchema.parse(input);
}

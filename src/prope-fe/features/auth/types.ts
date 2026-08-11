import { z } from 'zod';

export const userRoleSchema = z.enum(['owner', 'reviewer', 'viewer', 'admin']);

export const sessionSchema = z.object({
  id: z.string(),
  expiresAt: z.string(),
  user: z.object({
    id: z.string(),
    displayName: z.string(),
    email: z.email(),
    role: userRoleSchema,
    workspaceName: z.string(),
  }),
});

export type Session = z.infer<typeof sessionSchema>;
export type UserRole = z.infer<typeof userRoleSchema>;

export interface LoginCredentials {
  email: string;
  password: string;
}

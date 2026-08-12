import { z } from 'zod';

export const userRoleSchema = z.enum(['owner', 'reviewer', 'viewer', 'admin']);

export const sessionSchema = z.object({
  id: z.string(),
  expiresAt: z.string(),
  mustChangePassword: z.boolean(),
  user: z.object({
    id: z.string(),
    displayName: z.string(),
    email: z.email(),
    role: userRoleSchema,
    workspaceName: z.string(),
  }),
});

export const sessionResponseSchema = z.object({
  id: z.string(),
  expires_at: z.string(),
  must_change_password: z.boolean(),
  user: z.object({
    id: z.string(),
    display_name: z.string(),
    email: z.email(),
    role: userRoleSchema,
    workspace_name: z.string(),
  }),
}).transform((session) => ({
  id: session.id,
  expiresAt: session.expires_at,
  mustChangePassword: session.must_change_password,
  user: {
    id: session.user.id,
    displayName: session.user.display_name,
    email: session.user.email,
    role: session.user.role,
    workspaceName: session.user.workspace_name,
  },
}));

export type Session = z.infer<typeof sessionSchema>;
export type UserRole = z.infer<typeof userRoleSchema>;

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface SignupCredentials {
  displayName: string;
  email: string;
  password: string;
}

export interface ChangePasswordCredentials {
  currentPassword: string;
  newPassword: string;
}

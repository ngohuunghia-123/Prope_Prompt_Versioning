import { z } from 'zod';

export const userRoleSchema = z.enum(['owner', 'reviewer', 'viewer', 'admin']);
export type UserRole = z.infer<typeof userRoleSchema>;

// The API reports the person's full set of role bindings, capitalized to match
// the backend `access_control.Role` enum (Owner/Reviewer/Viewer/Admin). A person
// can hold several, and the API deliberately does not pick "the" role — so the
// SPA chrome collapses the set to one for display, highest binding wins.
const apiRoleSchema = z.enum(['Owner', 'Reviewer', 'Viewer', 'Admin']);
const rolePriority: readonly UserRole[] = ['admin', 'owner', 'reviewer', 'viewer'];

function primaryRole(roles: Array<z.infer<typeof apiRoleSchema>>): UserRole {
  const held = roles.map((role) => role.toLowerCase() as UserRole);
  return rolePriority.find((role) => held.includes(role)) ?? 'viewer';
}

export const sessionSchema = z.object({
  id: z.string(),
  expiresAt: z.string(),
  mustChangePassword: z.boolean(),
  user: z.object({
    id: z.string(),
    displayName: z.string(),
    email: z.email(),
    role: userRoleSchema,
    // The API has always returned this; the client dropped it until the key
    // routes needed it. Every `/api/v1/workspaces/{id}/…` call is addressed by
    // it, and the alternative — a `GET /workspaces` to discover the one the
    // session is already scoped to — is a round trip to learn something the
    // session read just answered.
    workspaceId: z.string(),
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
    roles: z.array(apiRoleSchema),
    workspace_id: z.string(),
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
    role: primaryRole(session.user.roles),
    workspaceId: session.user.workspace_id,
    workspaceName: session.user.workspace_name,
  },
}));

export type Session = z.infer<typeof sessionSchema>;

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

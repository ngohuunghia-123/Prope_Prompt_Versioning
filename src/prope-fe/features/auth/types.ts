import { z } from 'zod';

/**
 * The wire values of `access.role_binding.role`, spelled exactly as the database
 * stores them.
 *
 * ADR-0053 rule 9: statuses and roles stay literal. `Admin` is a **value**, not a
 * word — it is stored as written, transmitted as written, and translated only at
 * the point of display. Lower-casing it here to match a catalogue key would make
 * this enum a display concern and would silently stop matching the API the day
 * somebody compared the two.
 */
export const roleSchema = z.enum(['Owner', 'Reviewer', 'Viewer', 'Admin']);

export type Role = z.infer<typeof roleSchema>;

/**
 * Which role to print when somebody holds several.
 *
 * A person's bindings are a set — `access.role_binding` has no uniqueness on
 * `user_id` — and the account chip has room for one line. Most-privileged wins,
 * because that is the one that explains what they can do; showing `Viewer` for an
 * Admin who also holds it would be true and useless.
 *
 * **This is a display rule and never an authorisation one.** Nothing in the SPA
 * may decide what to permit from this value: `may()` answers that per subject, on
 * the server, against a row it reads at the moment of the act (A-114). The client
 * asks and renders the refusal.
 */
const ROLE_PRECEDENCE: readonly Role[] = ['Admin', 'Owner', 'Reviewer', 'Viewer'];

export function primaryRole(roles: readonly Role[]): Role | undefined {
  return ROLE_PRECEDENCE.find((role) => roles.includes(role));
}

/** The i18n catalogue key for a role. The catalogue is keyed lower-case; the value is not. */
export function roleTranslationKey(role: Role): string {
  return `roles.${role.toLowerCase()}`;
}

const sessionUserSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  // Deliberately `z.string()` and not `z.email()`. The server's own rule is
  // bounded length, exactly one `@`, no whitespace — it treats an email as an
  // identifier rather than an address, because Prope has no outbound channel
  // (A-071). A stricter check here would reject a value the server accepted and
  // stored, which fails the sign-in of an account that exists.
  email: z.string(),
  roles: z.array(roleSchema),
  workspace_id: z.string(),
  workspace_name: z.string(),
});

/**
 * `SessionRead`, the one shape `POST /auth/login`, `POST /auth/register` and
 * `GET /auth/session` all answer with.
 *
 * `id` is **not** the session cookie. The cookie is `HttpOnly` and never reaches
 * a script (ADR-0029); this is a one-way digest of it, so the SPA can tell one
 * session from another across a re-authentication and nobody can authenticate
 * with what they read out of a response body.
 */
export const sessionResponseSchema = z
  .object({
    id: z.string(),
    expires_at: z.string(),
    must_change_password: z.boolean(),
    user: sessionUserSchema,
  })
  .transform((session) => ({
    id: session.id,
    expiresAt: session.expires_at,
    mustChangePassword: session.must_change_password,
    user: {
      id: session.user.id,
      displayName: session.user.display_name,
      email: session.user.email,
      roles: session.user.roles,
      workspaceId: session.user.workspace_id,
      workspaceName: session.user.workspace_name,
    },
  }));

export type Session = z.infer<typeof sessionResponseSchema>;

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

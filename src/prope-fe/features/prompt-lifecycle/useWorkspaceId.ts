import { useQuery } from '@tanstack/react-query';
import { sessionOptions } from '@/features/auth/queries';

/**
 * The workspace this session is in.
 *
 * **A session names exactly one workspace and there is no picker** — sign-in lands
 * in the oldest active membership, deterministically, and nothing moves a session
 * between tenants. So this is a constant for the life of a session, read from the
 * session rather than from a route parameter: a workspace id in the URL would be
 * a value a person could edit, and the server answers not-found for a workspace
 * that is not the session's anyway.
 *
 * It exists because the lifecycle query keys carry the workspace, so that a cache
 * populated before a re-authentication cannot be read after one.
 *
 * Returns an empty string while the session is loading. Every caller passes it
 * into a query that is `enabled` on it being non-empty, which is what stops a
 * request firing against a workspace nobody has named yet.
 */
export function useWorkspaceId(): string {
  const session = useQuery(sessionOptions);
  return session.data?.user.workspaceId ?? '';
}

import { apiRequest } from '@/lib/apiClient';
import { sessionResponseSchema, type Session } from '@/features/auth/types';
import {
  createdWorkspaceSchema,
  redeemedInviteSchema,
  workspaceMembershipListSchema,
  type CreatedWorkspace,
  type RedeemedInvite,
  type WorkspaceMembershipList,
} from '@/features/auth/lobbyTypes';

/**
 * The four routes a workspace-less session can reach, called for real.
 *
 * **No mock arm, deliberately** (`keysApi.ts`'s rule). A faked chooser would
 * offer workspaces that do not exist and a code that admits nobody — and the one
 * thing this screen has to get right is that joining actually worked. Offline,
 * these throw and the page says the stack is not running.
 *
 * **`enterWorkspace` is the only call in the product that changes the session
 * cookie after sign-in.** The server deletes the presented session row and mints
 * one naming the target workspace, because a cross-tenant `UPDATE ... SET
 * workspace_id` is refused by RLS from both sides. So the response is a whole
 * session envelope and the caller must replace its cached session with it rather
 * than patching a field.
 */

const dataMode =
  import.meta.env.VITE_DATA_MODE ??
  import.meta.env.VITE_AUTH_MODE ??
  'api';
const useRealApi = dataMode === 'api';

export class LobbyUnavailable extends Error {
  constructor() {
    super('The workspace chooser needs the real API — start the stack or set VITE_DATA_MODE=api');
    this.name = 'LobbyUnavailable';
  }
}

export function lobbyIsLive(): boolean {
  return useRealApi;
}

function requireRealApi(): void {
  if (!useRealApi) throw new LobbyUnavailable();
}

/** Every workspace this person is in or waiting on. Answered from the lobby too. */
export async function listMyWorkspaces(): Promise<WorkspaceMembershipList> {
  requireRealApi();
  return apiRequest('/api/v1/auth/workspaces', { schema: workspaceMembershipListSchema });
}

/** Bind the session to one workspace. Returns the new session; the cookie moves with it. */
export async function enterWorkspace(workspaceId: string): Promise<Session> {
  requireRealApi();
  return apiRequest(`/api/v1/auth/workspaces/${encodeURIComponent(workspaceId)}/enter`, {
    method: 'POST',
    schema: sessionResponseSchema,
  });
}

/**
 * Create a workspace. **It does not move the caller into it** — entering ends one
 * session and mints another, and folding that into creation would mean two
 * operations behind one button, with a failed second half leaving a workspace
 * that exists and a person who was not told they are still elsewhere.
 */
export async function createWorkspace(name: string): Promise<CreatedWorkspace> {
  requireRealApi();
  return apiRequest('/api/v1/workspaces', {
    method: 'POST',
    body: JSON.stringify({ name }),
    schema: createdWorkspaceSchema,
  });
}

/**
 * Present an invitation code.
 *
 * Every failure is one refusal — unknown, expired, revoked, exhausted and
 * rate-limited all answer `404 invite_not_redeemable`, byte for byte. The client
 * therefore has exactly one message to show, and inventing more specific ones
 * from the status code would be inventing information the server withheld on
 * purpose.
 */
export async function redeemInvite(code: string): Promise<RedeemedInvite> {
  requireRealApi();
  return apiRequest('/api/v1/auth/invites/redeem', {
    method: 'POST',
    body: JSON.stringify({ code }),
    schema: redeemedInviteSchema,
  });
}

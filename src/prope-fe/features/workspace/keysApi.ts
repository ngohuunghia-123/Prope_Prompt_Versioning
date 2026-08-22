import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import {
  apiKeySchema,
  createdApiKeySchema,
  type ApiKey,
  type CreatedApiKey,
  type KeyScope,
} from '@/features/workspace/keyTypes';

/**
 * `access_control`'s key routes, called for real.
 *
 * **No mock arm, for `evalApi.ts`'s reason and one more.** A faked key is a
 * screen handing somebody a credential that authenticates nothing — they would
 * paste it into their app and debug a 401 for an hour. Offline, these throw, and
 * the pages that use them say the stack is not running.
 */

const dataMode =
  import.meta.env.VITE_DATA_MODE ??
  import.meta.env.VITE_AUTH_MODE ??
  'api';
const useRealApi = dataMode === 'api';

export class KeysUnavailable extends Error {
  constructor() {
    super('API keys need the real API — start the stack or set VITE_DATA_MODE=api');
    this.name = 'KeysUnavailable';
  }
}

export function keysAreLive(): boolean {
  return useRealApi;
}

function requireRealApi(): void {
  if (!useRealApi) throw new KeysUnavailable();
}

function base(workspaceId: string): string {
  return `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/keys`;
}

export async function listKeys(workspaceId: string): Promise<ApiKey[]> {
  requireRealApi();
  return apiRequest(base(workspaceId), { schema: z.array(apiKeySchema) });
}

/**
 * Mint a key. **The response is the only time the secret exists outside a
 * provider's Authorization header** — the caller must show it once and must not
 * persist it.
 */
export async function createKey(
  workspaceId: string,
  input: { name: string; scopeModelNames: string[]; scopeNamespaces: string[] },
): Promise<CreatedApiKey> {
  requireRealApi();
  return apiRequest(base(workspaceId), {
    method: 'POST',
    body: JSON.stringify({
      name: input.name,
      scope_model_names: input.scopeModelNames,
      // A-158. One folder here replaces the thousand model names a product that
      // owns one would otherwise have to be granted, and it keeps replacing them
      // as prompts are added — which is the whole point: a key scoped to a folder
      // does not need re-granting when the folder grows.
      scope_namespaces: input.scopeNamespaces,
    }),
    schema: createdApiKeySchema,
  });
}

/**
 * Replace what a key may reach. Wholesale, never a delta — the server takes the
 * whole list for the same reason the dataset attachments PUT does, so the caller
 * sends the array it wants to end up with.
 */
export async function setKeyScope(
  workspaceId: string,
  keyId: string,
  scope: KeyScope,
): Promise<ApiKey> {
  requireRealApi();
  return apiRequest(`${base(workspaceId)}/${encodeURIComponent(keyId)}/scope`, {
    method: 'PUT',
    body: JSON.stringify({
      scope_model_names: scope.scopeModelNames,
      scope_namespaces: scope.scopeNamespaces,
      // Sent even when null, and that is the contract rather than an oversight:
      // omitting them clears them, so a screen that means "leave observation on"
      // has to say so every time. See `KeyScope`.
      observe_provider_config_id: scope.observeProviderConfigId,
      observe_namespace: scope.observeNamespace,
    }),
    schema: apiKeySchema,
  });
}

/** Revoke. Effective on the very next request; the row survives with a timestamp. */
export async function revokeKey(workspaceId: string, keyId: string): Promise<void> {
  requireRealApi();
  await apiRequest(`${base(workspaceId)}/${encodeURIComponent(keyId)}`, { method: 'DELETE' });
}

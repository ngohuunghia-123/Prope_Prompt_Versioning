import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import {
  routerComboSchema,
  type RouterCombo,
  type RouterComboWriteInput,
} from '@/features/prompt-lifecycle/routerComboTypes';

/**
 * Router combos, called for real — ADR-0069.
 *
 * The mock arm follows `providerApi.ts` exactly, and for the same reason: a
 * combo names provider configurations by id, and faking one would be a screen
 * offering to route traffic to providers that do not exist. Reads answer
 * "none", which is a state every caller already renders; writes throw.
 */

const dataMode = import.meta.env.VITE_DATA_MODE ?? import.meta.env.VITE_AUTH_MODE ?? 'api';
const useRealApi = dataMode === 'api';

/** Thrown rather than faked, and caught by the page into a catalogue key. */
export class RoutingUnavailable extends Error {
  constructor() {
    super('router combos need the real API — start the stack or set VITE_DATA_MODE=api');
    this.name = 'RoutingUnavailable';
  }
}

function requireRealApi(): void {
  if (!useRealApi) throw new RoutingUnavailable();
}

export function isRoutingUnavailable(error: unknown): error is RoutingUnavailable {
  return error instanceof RoutingUnavailable;
}

/**
 * The rungs come back inline with the list, so the composer's select can render
 * `1. OpenAI · gpt-4o-mini → 2. Azure · gpt-4o` under it without a second call.
 * A combo name alone tells the author nothing about what they are choosing.
 */
export async function getRouterCombos(): Promise<RouterCombo[]> {
  if (!useRealApi) return [];
  return apiRequest('/api/v1/router-combos', { schema: z.array(routerComboSchema) });
}

export async function getRouterCombo(comboId: string): Promise<RouterCombo> {
  requireRealApi();
  return apiRequest(`/api/v1/router-combos/${encodeURIComponent(comboId)}`, {
    schema: routerComboSchema,
  });
}

function writeBody(input: RouterComboWriteInput): string {
  return JSON.stringify({
    display_name: input.displayName,
    description: input.description,
    // No `priority` field: the index is the priority, which is what the server
    // takes. Sending one would let the array and the number disagree.
    entries: input.entries.map((entry) => ({
      provider_config_id: entry.providerConfigId,
      upstream_model: entry.upstreamModel,
    })),
  });
}

export async function createRouterCombo(input: RouterComboWriteInput): Promise<RouterCombo> {
  requireRealApi();
  return apiRequest('/api/v1/router-combos', {
    method: 'POST',
    body: writeBody(input),
    schema: routerComboSchema,
  });
}

/**
 * `PUT`, never `PATCH`. The rungs are an ordered list and the server replaces
 * them wholesale — deleted and reinserted inside one transaction, which is why
 * the table carries DELETE and never UPDATE.
 *
 * This does **not** touch any revision already bound to the combo. Every one of
 * them holds its own frozen copy, and adopting an edit takes a new revision and
 * a new approval.
 */
export async function replaceRouterCombo(
  comboId: string,
  input: RouterComboWriteInput,
): Promise<RouterCombo> {
  requireRealApi();
  return apiRequest(`/api/v1/router-combos/${encodeURIComponent(comboId)}`, {
    method: 'PUT',
    body: writeBody(input),
    schema: routerComboSchema,
  });
}

/**
 * Deleting a template is always allowed and never breaks a released prompt —
 * the revision keeps its snapshot, and `route_combo_id` on the revision is a
 * value with no foreign key precisely so this stays true.
 */
export async function deleteRouterCombo(comboId: string): Promise<void> {
  requireRealApi();
  await apiRequest(`/api/v1/router-combos/${encodeURIComponent(comboId)}`, { method: 'DELETE' });
}

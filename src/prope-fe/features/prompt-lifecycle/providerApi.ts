import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import {
  catalogueRefreshSchema,
  priceRowPageSchema,
  providerModelSchema,
  providerReadSchema,
  verificationReadSchema,
  PRICE_UNIT_SCALE,
  type CatalogueRefresh,
  type ModelAddInput,
  type PriceCreateInput,
  type PriceRow,
  type ProviderCreateInput,
  type ProviderModel,
  type ProviderRead,
  type ProviderUpdateInput,
  type VerificationRead,
} from '@/features/prompt-lifecycle/providerTypes';

/**
 * `provider_access` and the ledger's price table, called for real.
 *
 * There is no mock arm in this file. A provider configuration is a credential
 * that gets encrypted, probed against a live endpoint and stored — a fake one
 * would be a screen that says "connected" about nothing, which is worse than a
 * screen that says the stack is not running.
 */

const dataMode = import.meta.env.VITE_DATA_MODE ?? import.meta.env.VITE_AUTH_MODE ?? 'api';
const useRealApi = dataMode === 'api';

/** Thrown rather than faked, and caught by the page into a catalogue key. */
export class ProvidersUnavailable extends Error {
  constructor() {
    super('provider registration needs the real API — start the stack or set VITE_DATA_MODE=api');
    this.name = 'ProvidersUnavailable';
  }
}

function requireRealApi(): void {
  if (!useRealApi) throw new ProvidersUnavailable();
}

export function isProvidersUnavailable(error: unknown): error is ProvidersUnavailable {
  return error instanceof ProvidersUnavailable;
}

export async function getProviderConfigs(): Promise<ProviderRead[]> {
  // A read is allowed to answer "none" offline: the composer asks for this list
  // on every new prompt, and an empty one is a state it already renders.
  if (!useRealApi) return [];
  return apiRequest('/api/v1/providers', { schema: z.array(providerReadSchema) });
}

export async function createProviderConfig(input: ProviderCreateInput): Promise<ProviderRead> {
  requireRealApi();
  return apiRequest('/api/v1/providers', {
    method: 'POST',
    body: JSON.stringify({
      display_name: input.displayName,
      base_url: input.baseUrl,
      credential: input.credential,
    }),
    schema: providerReadSchema,
  });
}

export async function updateProviderConfig(input: ProviderUpdateInput): Promise<ProviderRead> {
  requireRealApi();
  return apiRequest(`/api/v1/providers/${encodeURIComponent(input.providerId)}`, {
    method: 'PATCH',
    body: JSON.stringify({
      ...(input.displayName === undefined ? {} : { display_name: input.displayName }),
      ...(input.status === undefined ? {} : { status: input.status }),
    }),
    schema: providerReadSchema,
  });
}

export async function rotateProviderCredential(input: { providerId: string; credential: string }): Promise<ProviderRead> {
  requireRealApi();
  return apiRequest(`/api/v1/providers/${encodeURIComponent(input.providerId)}/credential`, {
    method: 'POST',
    body: JSON.stringify({ credential: input.credential }),
    schema: providerReadSchema,
  });
}

/** Re-probes with the stored secret and re-discovers the catalogue in one call. */
export async function verifyProviderConfig(providerId: string): Promise<VerificationRead> {
  requireRealApi();
  return apiRequest(`/api/v1/providers/${encodeURIComponent(providerId)}/verify`, {
    method: 'POST',
    schema: verificationReadSchema,
  });
}

export async function deleteProviderConfig(providerId: string): Promise<void> {
  requireRealApi();
  await apiRequest(`/api/v1/providers/${encodeURIComponent(providerId)}`, { method: 'DELETE' });
}

export async function getProviderModels(providerId: string): Promise<ProviderModel[]> {
  if (!useRealApi) return [];
  return apiRequest(`/api/v1/providers/${encodeURIComponent(providerId)}/models`, {
    schema: z.array(providerModelSchema),
  });
}

export async function refreshProviderModels(providerId: string): Promise<CatalogueRefresh> {
  requireRealApi();
  return apiRequest(`/api/v1/providers/${encodeURIComponent(providerId)}/models/refresh`, {
    method: 'POST',
    schema: catalogueRefreshSchema,
  });
}

export async function addProviderModel(input: ModelAddInput): Promise<ProviderModel> {
  requireRealApi();
  return apiRequest(`/api/v1/providers/${encodeURIComponent(input.providerId)}/models`, {
    method: 'POST',
    body: JSON.stringify({
      model_id: input.modelId,
      ...(input.displayName ? { display_name: input.displayName } : {}),
    }),
    schema: providerModelSchema,
  });
}

/**
 * Every price row the workspace has, newest page first.
 *
 * Superseded rows come back too and that is deliberate on the server's side
 * (A-102) — a cost recorded under an old price has to stay explicable. The page
 * that renders this keeps only the row in force, which is the one whose
 * `effective_to` is null.
 */
export async function getPriceRows(): Promise<PriceRow[]> {
  if (!useRealApi) return [];
  const page = await apiRequest('/api/v1/prices', { schema: priceRowPageSchema });
  return page.items;
}

/**
 * Append a price. Never an edit — the table is insert-only, and superseding a
 * figure is a new row with a later `effective_from`.
 *
 * `effective_from` is now rather than a field on the form. Backdating is what
 * the endpoint is for (a price added after calls have accrued, then repriced),
 * but that is a ledger correction and not something the provider screen should
 * quietly offer while somebody is typing in a vendor's rate card.
 */
export async function createPriceRow(input: PriceCreateInput): Promise<void> {
  requireRealApi();
  await apiRequest('/api/v1/prices', {
    method: 'POST',
    body: JSON.stringify({
      provider_config_id: input.providerId,
      upstream_model: input.upstreamModel,
      input_price_per_1k: input.inputPerMillion / PRICE_UNIT_SCALE,
      output_price_per_1k: input.outputPerMillion / PRICE_UNIT_SCALE,
      // Not divided: a per-request floor is not a token rate.
      minimum_charge_per_request: input.minimumPerRequest,
      currency: input.currency,
      effective_from: new Date().toISOString(),
    }),
  });
}

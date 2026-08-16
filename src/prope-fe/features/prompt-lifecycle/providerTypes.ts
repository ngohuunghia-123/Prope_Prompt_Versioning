import { z } from 'zod';

/**
 * Wire shapes for the real `provider_access` module — `src/prope/provider_access
 * /schemas.py`. Field names stay snake_case because they are the contract, not
 * the app model.
 *
 * There is no field carrying the credential anywhere in here, and that is the
 * module's central promise rather than an oversight: the secret is write-only
 * across the whole seam, and `credential_last_four` is all a read ever gets.
 */

export const providerReadSchema = z.object({
  provider_config_id: z.string(),
  display_name: z.string(),
  adapter: z.literal('openai_compatible'),
  base_url: z.string(),
  status: z.enum(['active', 'disabled']),
  verification_status: z.enum(['pending', 'passed', 'failed']),
  last_verified_at: z.string().nullable().optional(),
  verification_error: z.string().nullable().optional(),
  credential_last_four: z.string().nullable().optional(),
  interactive_concurrency: z.number().int(),
  batch_concurrency: z.number().int(),
  created_by: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const providerModelSchema = z.object({
  model_id: z.string(),
  display_name: z.string().nullable().optional(),
  supports_streaming: z.boolean(),
  available: z.boolean(),
  source: z.enum(['discovered', 'manual']),
});

export const verificationReadSchema = z.object({
  provider_config_id: z.string(),
  verification_status: z.enum(['pending', 'passed', 'failed']),
  last_verified_at: z.string().nullable().optional(),
  verification_error: z.string().nullable().optional(),
  models_discovered: z.number().int(),
});

export const catalogueRefreshSchema = z.object({
  provider_config_id: z.string(),
  discovered: z.number().int(),
});

// `input_price_per_1k` and `output_price_per_1k` arrive as JSON numbers from a
// server-side Decimal. They are read back only to show what is currently in
// force, never to compute a bill — the ledger prices its own rows.
export const priceRowSchema = z.object({
  price_row_id: z.string(),
  provider_config_id: z.string(),
  upstream_model: z.string(),
  input_price_per_1k: z.coerce.number(),
  output_price_per_1k: z.coerce.number(),
  // Per request, not per 1k, so nothing scales it by PRICE_UNIT_SCALE. Zero
  // means no floor, which is what every row created before it existed carries.
  minimum_charge_per_request: z.coerce.number(),
  currency: z.string(),
  effective_from: z.string(),
  effective_to: z.string().nullable().optional(),
});

export const priceRowPageSchema = z.object({
  items: z.array(priceRowSchema),
  next_cursor: z.string().nullable().optional(),
});

export type ProviderRead = z.infer<typeof providerReadSchema>;
export type ProviderModel = z.infer<typeof providerModelSchema>;
export type VerificationRead = z.infer<typeof verificationReadSchema>;
export type CatalogueRefresh = z.infer<typeof catalogueRefreshSchema>;
export type PriceRow = z.infer<typeof priceRowSchema>;

/**
 * The vendors offered on the registration form.
 *
 * `provider_access` has exactly one adapter — `openai_compatible` — so a preset
 * is not a different code path. It is a base URL and a name, filled in so that
 * registering OpenAI does not require anybody to remember where `/v1` goes. All
 * four of these publish an OpenAI-compatible endpoint; `custom` is the one that
 * asks for the URL because it is the only one that cannot be known in advance.
 */
export interface ProviderPreset {
  id: 'openai' | 'anthropic' | 'gemini' | 'openrouter' | 'custom';
  label: string;
  baseUrl: string;
}

export const PROVIDER_PRESETS: readonly ProviderPreset[] = [
  { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
  { id: 'anthropic', label: 'Anthropic', baseUrl: 'https://api.anthropic.com/v1' },
  { id: 'gemini', label: 'Google Gemini', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai' },
  { id: 'openrouter', label: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1' },
  { id: 'custom', label: 'OpenAI-compatible', baseUrl: '' },
] as const;

export interface ProviderCreateInput {
  displayName: string;
  baseUrl: string;
  credential: string;
}

export interface ProviderUpdateInput {
  providerId: string;
  displayName?: string;
  status?: 'active' | 'disabled';
}

export interface ModelAddInput {
  providerId: string;
  modelId: string;
  displayName?: string;
}

/**
 * A price, as the form takes it.
 *
 * Vendors publish per-1M pricing and `POST /api/v1/prices` stores per-1k, so the
 * division happens at the edge — once, here, rather than in whichever component
 * happens to render a figure.
 *
 * `minimumPerRequest` is the one figure that is **not** rescaled: it is a floor
 * under one call's whole cost, so a request that prices below it is charged it
 * instead. Zero is the normal value and means no floor.
 */
export interface PriceCreateInput {
  providerId: string;
  upstreamModel: string;
  inputPerMillion: number;
  outputPerMillion: number;
  minimumPerRequest: number;
  currency: string;
}

export const PRICE_UNIT_SCALE = 1000;

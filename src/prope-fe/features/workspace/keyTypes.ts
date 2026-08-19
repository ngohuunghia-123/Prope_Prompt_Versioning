import { z } from 'zod';

/**
 * Consumer API keys, as `access_control` returns them.
 *
 * **`secret` exists on exactly one shape and that is not an accident.** The
 * plaintext appears in the creation response and nowhere else, ever — the stored
 * row keeps a SHA-256 digest and four display characters, so no later read can
 * reconstruct it. Two schemas rather than one optional field, because an optional
 * `secret` is a field a component would eventually try to render from a list.
 */

export const apiKeySchema = z
  .object({
    key_id: z.string(),
    name: z.string(),
    last_four: z.string(),
    scope_model_names: z.array(z.string()),
    // ADR-0061 / A-158. Defaulted rather than required so a client built against
    // the pre-namespace API still parses — the server always sends it now, and
    // the default is the same default-deny empty list the column holds.
    scope_namespaces: z.array(z.string()).default([]),
    // ADR-0059's pair. `observe_provider_config_id` names a CONFIGURATION, never
    // a credential, so reading it back discloses nothing the providers screen
    // does not already show.
    observe_provider_config_id: z.string().nullable().optional(),
    observe_namespace: z.string().nullable().optional(),
    created_by: z.string(),
    created_at: z.string(),
    revoked_at: z.string().nullable().optional(),
    last_used_at: z.string().nullable().optional(),
  })
  .transform((key) => ({
    keyId: key.key_id,
    name: key.name,
    lastFour: key.last_four,
    scopeModelNames: key.scope_model_names,
    scopeNamespaces: key.scope_namespaces,
    observeProviderConfigId: key.observe_provider_config_id ?? null,
    observeNamespace: key.observe_namespace ?? null,
    createdBy: key.created_by,
    createdAt: key.created_at,
    revokedAt: key.revoked_at ?? null,
    lastUsedAt: key.last_used_at ?? null,
  }));

export type ApiKey = z.infer<typeof apiKeySchema>;

export const createdApiKeySchema = z
  .object({
    key_id: z.string(),
    name: z.string(),
    last_four: z.string(),
    scope_model_names: z.array(z.string()),
    scope_namespaces: z.array(z.string()).default([]),
    created_at: z.string(),
    secret: z.string(),
  })
  .transform((key) => ({
    keyId: key.key_id,
    name: key.name,
    lastFour: key.last_four,
    scopeModelNames: key.scope_model_names,
    scopeNamespaces: key.scope_namespaces,
    createdAt: key.created_at,
    secret: key.secret,
  }));

export type CreatedApiKey = z.infer<typeof createdApiKeySchema>;

/**
 * The attribution bucket for calls no key made — playground trials and eval runs.
 *
 * **It is not a key, and nothing mints one.** The playground used to create an
 * `Others` key on first use, which was wrong twice over: it implied a trial needs
 * a credential, and it put a real, exportable secret behind an action nobody took
 * deliberately. A trial authenticates with the person's session; the ledger tells
 * it apart by `source`, and `ck_call_record_playground_calls_are_internal`
 * *refuses* a playground row that names a key at all.
 *
 * So the lifetime question does not arise. There is no internal credential to
 * persist for a session, rotate between sessions, leak, or revoke — the strongest
 * version of "internal only", because it is a property of the schema rather than
 * a rule somebody has to keep enforcing.
 *
 * A literal rather than a translated string: it labels a bucket that groups
 * ledger rows, and a name that changed with the interface language would split
 * one bucket in two the day somebody switched locales. ADR-0053 keys *display*
 * strings; this is a value.
 */
export const INTERNAL_APP_LABEL = 'Internal';

/**
 * What `PUT .../scope` takes, and it is the whole reach in one object.
 *
 * **Wholesale, never a delta**, which is why this is one type and not four
 * optional fields: the server replaces everything this names, so a caller that
 * omits `observeNamespace` is *turning observation off*, not leaving it alone.
 * That is the safe direction for a capability whose failure mode is "traffic
 * quietly went somewhere", and modelling it as one required object is what stops
 * a screen from half-sending it by accident.
 *
 * The observe pair is set together or not at all — `null` on both, or a string
 * on both. `ck_api_key_observe_is_all_or_nothing` refuses the half-set pair
 * underneath, and the command refuses it with a 422 before that.
 */
export interface KeyScope {
  scopeModelNames: string[];
  scopeNamespaces: string[];
  observeProviderConfigId: string | null;
  observeNamespace: string | null;
}

export function isKeyLive(key: ApiKey): boolean {
  return key.revokedAt === null;
}

/** True when the key forwards what the registry cannot resolve. ADR-0059. */
export function keyObserves(key: ApiKey): boolean {
  return key.observeProviderConfigId !== null && key.observeNamespace !== null;
}

/** Masked for display. The real secret is unrecoverable, so this is all a list can show. */
export function maskedKey(key: ApiKey): string {
  return `prope_${key.keyId}_${'•'.repeat(8)}${key.lastFour}`;
}

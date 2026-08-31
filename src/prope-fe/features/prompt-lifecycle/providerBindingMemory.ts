import { z } from 'zod';

/**
 * The provider configuration and upstream model this browser last committed.
 *
 * Registering a prompt asks the same two questions every time, and for most
 * workspaces the answer is the same every time: one provider, one model, chosen
 * once and repeated for every prompt after it. Re-picking them is the only part
 * of the composer that is pure repetition — the title, the body and the change
 * summary are all genuinely per-prompt.
 *
 * **A convenience, never a decision.** What is stored is offered as a default
 * into an empty binding and nothing else. It never overwrites a binding that is
 * already set, so opening an existing revision shows what that revision binds
 * to; and it is applied only after `provider_access` has confirmed the
 * configuration still exists, so a provider that was deleted — or one belonging
 * to a workspace this person has since left — silently stops being offered
 * rather than being carried into a 422 on save.
 *
 * Per browser rather than per workspace, and deliberately not per person: this
 * is `localStorage`, so it is already scoped to the machine somebody sits at,
 * and a value that fails the existence check costs one skipped prefill. Storing
 * it under a workspace id would imply a guarantee the storage cannot give.
 *
 * Nothing here is confidential. A `provider_config_id` is an opaque identifier
 * and a model id is a public catalogue name — credentials are workspace-supplied
 * and never leave the server (they are not returned by any read API), so none of
 * this is a secret arriving somewhere it should not be.
 */
const STORAGE_KEY = 'prope-last-provider-binding';

/** Both halves or neither, mirroring `ck_revision_binding_is_whole`. A stored
 * half-binding could only ever prefill a form into the invalid state the
 * database refuses, so it is treated as unreadable. */
const bindingSchema = z.object({
  providerConfigId: z.string().min(1),
  upstreamModel: z.string().min(1),
});

export type RememberedProviderBinding = z.infer<typeof bindingSchema>;

/** What was last saved, or `undefined` if nothing readable is stored.
 *
 * An unparseable entry is removed on the way past rather than left to fail the
 * same way on every future read. */
export function readLastProviderBinding(): RememberedProviderBinding | undefined {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    // localStorage unavailable (private mode, blocked site data) — no memory.
    return undefined;
  }
  if (!raw) return undefined;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    clearLastProviderBinding();
    return undefined;
  }

  const result = bindingSchema.safeParse(parsed);
  if (!result.success) {
    clearLastProviderBinding();
    return undefined;
  }
  return result.data;
}

/**
 * Record a binding that was actually written.
 *
 * Called on a successful save rather than when the selects change, because
 * "last used" should mean a revision was created with it. A provider somebody
 * picked, reconsidered and cleared is not what they use, and offering it back
 * on the next prompt would make an abandoned choice sticky.
 *
 * A half-binding is a no-op, not a partial write: the pair is unset together
 * (a workspace with no provider registered yet can still create prompts), and
 * storing half of it would overwrite a good memory with one that cannot be used.
 */
export function rememberProviderBinding(binding: { providerConfigId: string; upstreamModel: string }): void {
  const result = bindingSchema.safeParse(binding);
  if (!result.success) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(result.data));
  } catch {
    // Quota or unavailable storage. The composer works without the memory, so a
    // failure here is worth nothing more than not having remembered.
  }
}

export function clearLastProviderBinding(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear if storage cannot be reached.
  }
}

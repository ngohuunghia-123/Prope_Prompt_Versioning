import { z } from 'zod';

/**
 * The router combo this browser last committed — ADR-0069.
 *
 * Structurally identical to `providerBindingMemory`, and a **separate key** on
 * purpose. One combined record would have to hold two memories with different
 * validity lifetimes: a combo can be deleted while the pair stays perfectly
 * good, and a record whose halves expire independently has to be either thrown
 * away whole or partially trusted — and the existing module explicitly refuses
 * to partially trust a half-binding.
 *
 * There is also **no third key for the mode**, because a mode with nothing
 * behind it is not a memory. If the last save used a combo, this key exists,
 * and that *is* the mode. The honest cost: somebody who alternates between a
 * pair and a combo pays one extra click each time.
 *
 * Nothing here is confidential. A combo id is an opaque identifier; the rungs
 * it names are not stored at all.
 */
const STORAGE_KEY = 'prope-last-router-combo';

const comboSchema = z.object({
  routeComboId: z.string().min(1),
});

export type RememberedRouterCombo = z.infer<typeof comboSchema>;

/**
 * What was last saved, or `undefined` if nothing readable is stored.
 *
 * An unparseable entry is removed on the way past rather than left to fail the
 * same way on every future read.
 */
export function readLastRouterCombo(): RememberedRouterCombo | undefined {
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
    clearLastRouterCombo();
    return undefined;
  }

  const result = comboSchema.safeParse(parsed);
  if (!result.success) {
    clearLastRouterCombo();
    return undefined;
  }
  return result.data;
}

/**
 * Record a combo that was actually written.
 *
 * Called on a successful save, like its sibling — "last used" means a revision
 * was created against it, not that somebody opened the select and looked.
 *
 * The caller is what clears the *other* memory. Doing the cross-clear inside
 * either module would make the two import each other for a rule that belongs to
 * whoever knows which mode was saved.
 */
export function rememberRouterCombo(routeComboId: string): void {
  const result = comboSchema.safeParse({ routeComboId });
  if (!result.success) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(result.data));
  } catch {
    // Quota or unavailable storage. The composer works without the memory.
  }
}

export function clearLastRouterCombo(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear if storage cannot be reached.
  }
}

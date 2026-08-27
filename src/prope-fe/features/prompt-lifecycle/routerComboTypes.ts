import { z } from 'zod';

/**
 * Wire shapes for router combos — `src/prope/prompt_registry/schemas.py`,
 * ADR-0069. Field names stay snake_case because they are the contract.
 *
 * **Naming.** The wire says `route`; this app says `combo`. `route` already
 * means react-router in every other file here, and a `RouteEntry` beside a
 * `<Route>` is a sentence nobody can read twice the same way. The translation
 * happens once, at this boundary.
 *
 * A combo is a **template**. Binding a revision to one copies its rungs into
 * that revision, frozen — editing the template afterwards changes nothing
 * already released. That rule is not enforced anywhere on this side; it is the
 * database's, by privilege. What this side must do is *say* so, which is why
 * `revision_count` is read back at all.
 */

export const routerComboEntrySchema = z.object({
  priority: z.number().int(),
  provider_config_id: z.string(),
  upstream_model: z.string(),
});

export const routerComboSchema = z.object({
  combo_id: z.string(),
  display_name: z.string(),
  description: z.string(),
  entries: z.array(routerComboEntrySchema),
  created_by: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  // How many revisions were snapshotted from this template. Nothing is blocked
  // by it — a delete is always allowed — but it is the number that lets the
  // edit dialog's "this changes nothing already released" be believed.
  revision_count: z.number().int(),
});

export type RouterComboEntry = z.infer<typeof routerComboEntrySchema>;
export type RouterCombo = z.infer<typeof routerComboSchema>;

/**
 * One rung as the form holds it.
 *
 * `priority` is absent on purpose, matching `RouterComboEntryWrite`: the rung's
 * index in the array is its priority. A number the user can type is a number
 * two rungs can share, and then the array and the field disagree about the
 * order with no way to say which is right.
 */
export interface RouterComboEntryInput {
  providerConfigId: string;
  upstreamModel: string;
}

export interface RouterComboWriteInput {
  displayName: string;
  description: string;
  entries: RouterComboEntryInput[];
}

/**
 * At least two, because a one-rung combo is today's single binding wearing a
 * new name — and it would be a name the reviewer has to open a second screen to
 * read. At most five, which is `ck_router_combo_entry_priority_bounded`.
 */
export const MIN_COMBO_ENTRIES = 2;
export const MAX_COMBO_ENTRIES = 5;

/**
 * The refusals this feature can produce, as `ErrorCode` spells them.
 *
 * Rendered through the catalogue by key. An unlisted code degrades to the
 * generic message rather than printing the server's English, which is the same
 * contract `readinessRules` keeps and the reason ADR-0053 has the API return a
 * machine `code` at all.
 */
export const ROUTER_COMBO_ERROR_CODES = [
  'registry_unknown_router_combo',
  'registry_router_combo_empty',
  'registry_router_combo_name_taken',
] as const;

export type RouterComboErrorCode = (typeof ROUTER_COMBO_ERROR_CODES)[number];

export function isRouterComboErrorCode(code: string): code is RouterComboErrorCode {
  return (ROUTER_COMBO_ERROR_CODES as readonly string[]).includes(code);
}

/**
 * Fold a display name down to A-021's namespace shape.
 *
 * ADR-0053 makes Vietnamese the one interface language, so the name a Prompt
 * Owner types is `Hỗ trợ khách hàng` — and the slug it becomes is the first half
 * of the model name a developer puts into an OpenAI client. The registry's
 * `NAME_PATTERN` is `^[a-z0-9][a-z0-9._-]{0,62}$`: ASCII, lower case, no
 * diacritics, so the fold is not cosmetic.
 *
 * This is a **suggestion**, never the stored value. The dialog shows the result
 * in an editable field beside a `slug/<name>` preview, because `ho-tro-khach-hang`
 * is a defensible default and a poor public API name, and the person who cares
 * about the difference should be able to type `support` instead.
 */

/**
 * `đ` and `Đ` are the reason `NFD` alone is not enough: Unicode decomposition
 * splits `ề` into `e` plus two combining marks, but `đ` is a letter in its own
 * right with no ASCII base to strip back to. Vietnamese without this line loses
 * the character entirely rather than folding it.
 */
const STANDALONE_LETTERS: Record<string, string> = { đ: 'd', Đ: 'd' };

const MAX_SLUG_LENGTH = 63;

export function slugify(value: string): string {
  const folded = [...value.normalize('NFD')]
    .map((character) => STANDALONE_LETTERS[character] ?? character)
    // Combining marks, which is what NFD just separated out.
    .filter((character) => !/\p{M}/u.test(character))
    .join('')
    .toLowerCase();

  return (
    folded
      // Everything the pattern does not admit becomes a separator, then runs of
      // separators collapse — so `Hỗ trợ  (KH)` gives `ho-tro-kh`, not
      // `ho-tro---kh-`.
      .replace(/[^a-z0-9._-]+/g, '-')
      .replace(/-{2,}/g, '-')
      // The pattern's first character is alphanumeric, so a leading `.`, `_` or
      // `-` is not merely ugly — it is refused by the database.
      .replace(/^[._-]+/, '')
      .replace(/[._-]+$/, '')
      .slice(0, MAX_SLUG_LENGTH)
      // Slicing can re-expose a trailing separator that was legal mid-string.
      .replace(/[._-]+$/, '')
  );
}

/**
 * `NAME_PATTERN` from `prope.prompt_registry.domain`, which is also the folder
 * table's `ck_folder_slug_shape`. Exported because both halves of a model name
 * are held to it — the folder dialog's slug field and the composer's name field
 * — and two copies of a regex are two chances to disagree with the database.
 */
export const SLUG_PATTERN = /^[a-z0-9][a-z0-9._-]{0,62}$/;

/** Whether a slug is one the registry will accept. Mirrors `NAME_PATTERN`. */
export function isValidSlug(value: string): boolean {
  return SLUG_PATTERN.test(value);
}

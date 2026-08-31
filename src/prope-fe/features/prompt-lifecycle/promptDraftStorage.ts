import { z } from 'zod';
import { promptSourceFormatSchema, type PromptEditorValues } from '@/features/prompt-lifecycle/types';

/**
 * The composer's form, kept across a closed tab.
 *
 * Registering a prompt is the one screen in the app where a person types for
 * ten minutes before anything exists server-side: the duplicate check, the XML
 * conversion and the write all happen on the press of "Đánh giá", so until then
 * the whole thing lives in `useForm` and a refresh takes it with it. There is no
 * draft row to fall back on and there deliberately isn't one — a revision is
 * immutable from the moment it is written (A-021), so the registry has no
 * half-written state to hold. That leaves the browser as the only place a
 * half-written *form* can live.
 *
 * Kept per folder rather than per person: the folder is the namespace, A-021
 * makes it permanent, and a draft begun in `marketing` has no meaning in
 * `support`. One draft per folder — starting a second prompt in the same folder
 * replaces the first, which is the same rule the composer itself has.
 */
const STORAGE_PREFIX = 'prope-prompt-draft:';

/** Fired after any write or clear, so a page listing drafts can re-read them.
 * `storage` only fires in OTHER tabs, which is the wrong half of the problem. */
export const PROMPT_DRAFTS_CHANGED = 'prope-prompt-drafts-changed';

/** How long an untouched draft stays offerable. Past this it is noise: the
 * prompt it was for has usually been written by hand somewhere else, and
 * restoring a month-old body over an empty composer is a surprise, not a
 * rescue. */
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

/**
 * Every field the composer holds, all optional.
 *
 * Deliberately NOT `promptEditorSchema`: that schema is the gate for writing a
 * revision — 20 characters of body, parseable XML, a whole provider binding —
 * and a draft that had to pass it could only be saved once it was finished.
 * What is stored is the state of a form mid-typing, so the only thing checked
 * here is that each field is still the shape the form expects. Anything else is
 * dropped rather than restored as `undefined` into a controlled input.
 */
const draftValuesSchema = z
  .object({
    title: z.string(),
    namespace: z.string(),
    name: z.string(),
    access: z.enum(['private', 'workspace']),
    providerConfigId: z.string(),
    upstreamModel: z.string(),
    // ADR-0069. This object is `.partial()`, so leaving these two out would
    // compile, pass every test, and silently strip the combo choice from every
    // restored draft — a field that is merely absent here is a field the
    // restore quietly discards.
    bindingMode: z.enum(['single', 'combo']),
    routeComboId: z.string(),
    promptBody: z.string(),
    fallbackAnswer: z.string(),
    changeSummary: z.string(),
    tags: z.array(z.string()),
    sourceMode: z.enum(['existing', 'authored']),
    sourceText: z.string(),
    sourceFormat: promptSourceFormatSchema,
    sourceFilename: z.string(),
  })
  .partial();

const storedDraftSchema = z.object({
  /** ISO, and the only thing the banner shows. A draft with no timestamp cannot
   * say how old it is, so it is treated as unreadable rather than as new. */
  savedAt: z.string().min(1),
  /** What the folder page lists it as, without having to parse the body. */
  title: z.string(),
  values: draftValuesSchema,
});

export type PromptDraftValues = z.infer<typeof draftValuesSchema>;
export type StoredPromptDraft = z.infer<typeof storedDraftSchema>;

/** The key a folder's draft lives under. */
export function promptDraftKey(namespace: string): string {
  return `${STORAGE_PREFIX}${namespace}`;
}

function announce(): void {
  try {
    window.dispatchEvent(new Event(PROMPT_DRAFTS_CHANGED));
  } catch {
    // Nothing is listening in a non-DOM context — ignore.
  }
}

export function clearPromptDraft(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // localStorage unavailable — ignore.
  }
  announce();
}

/**
 * The draft under `key`, or `undefined` if there is none, it cannot be parsed,
 * or it has aged out. An unreadable or expired entry is deleted on the way
 * past: leaving it would mean re-parsing the same broken JSON on every read.
 */
export function readPromptDraft(key: string): StoredPromptDraft | undefined {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(key);
  } catch {
    return undefined;
  }
  if (!raw) return undefined;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    clearPromptDraft(key);
    return undefined;
  }

  const result = storedDraftSchema.safeParse(parsed);
  if (!result.success) {
    clearPromptDraft(key);
    return undefined;
  }

  const savedAt = Date.parse(result.data.savedAt);
  if (Number.isNaN(savedAt) || Date.now() - savedAt > MAX_AGE_MS) {
    clearPromptDraft(key);
    return undefined;
  }
  return result.data;
}

/**
 * Writes the form as it stands. `title` is lifted out so the folder page can
 * name the draft without reading `values`.
 *
 * A quota failure is swallowed on purpose. The draft is a convenience laid over
 * a flow that already works without it, and a composer that started throwing
 * because the browser is full would have taken away the thing it was added to
 * protect.
 */
export function writePromptDraft(key: string, values: PromptEditorValues): void {
  const draft: StoredPromptDraft = { savedAt: new Date().toISOString(), title: values.title, values };
  try {
    localStorage.setItem(key, JSON.stringify(draft));
  } catch {
    return;
  }
  announce();
}

import { useCallback, useEffect, useRef, useState } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import {
  clearPromptDraft,
  readPromptDraft,
  writePromptDraft,
} from '@/features/prompt-lifecycle/promptDraftStorage';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

/** How long typing has to stop before the draft is written. Long enough that a
 * sentence is one write rather than forty; short enough that a tab closed in
 * annoyance still loses at most the last word. */
const DEBOUNCE_MS = 600;

/**
 * Whether two forms hold the same thing.
 *
 * Key order comes from the order fields were registered, which is not the order
 * the defaults object was written in — so a plain `JSON.stringify` comparison
 * would report two identical forms as different. The key list is the union of
 * both sides so a field present-but-`undefined` on one of them still lines up.
 */
function sameForm(left: PromptEditorValues, right: PromptEditorValues): boolean {
  const keys = [...new Set([...Object.keys(left), ...Object.keys(right)])].sort();
  return JSON.stringify(left, keys) === JSON.stringify(right, keys);
}

export interface PromptDraft {
  /** When the restored draft was last written, or `undefined` if nothing was
   * restored. This is what puts the banner on screen. */
  restoredAt?: string;
  /** Throw the draft away and put the composer back to how it opens. */
  discard: () => void;
  /** Take the banner down and keep the draft. Dismissing the notice means "yes,
   * this is mine" — clearing storage here would delete the recovery the moment
   * somebody acknowledged it worked. */
  acknowledge: () => void;
  /** Forget the draft without touching the form — the prompt has been written,
   * so there is nothing left to recover. */
  clear: () => void;
}

/**
 * Keeps the composer's form in `localStorage` and puts it back on the way in.
 *
 * Two separate jobs, and only the second is conditional. The autosave runs for
 * as long as the composer is mounted. The restore happens once, on mount, and
 * only when there is something stored — a composer opened on a folder with no
 * draft behaves exactly as it did before.
 *
 * **`pinned` is not a convenience.** The namespace comes from the URL and A-021
 * makes it permanent, so a draft carrying a stale namespace must not be allowed
 * to put it back: that is how a prompt gets filed into a folder nobody opened.
 * Whatever is pinned wins over both the draft and the defaults.
 */
export function usePromptDraft(
  form: UseFormReturn<PromptEditorValues>,
  key: string,
  initialValues: PromptEditorValues,
  pinned: Partial<PromptEditorValues>,
  enabled = true,
): PromptDraft {
  const [restoredAt, setRestoredAt] = useState<string>();
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  // Set while the hook itself is writing to the form, so the watcher below does
  // not save what a discard just erased. Without it, `discard` resets the form,
  // the reset notifies the watcher, and the emptied form is written straight
  // back over the draft that was meant to be gone.
  const suppressed = useRef(false);
  // Read through refs so the effects below depend on the key alone. `form` is a
  // fresh object every render and `initialValues` is rebuilt by its caller, so
  // either one in a dependency list would re-run the restore on every keystroke.
  const formRef = useRef(form);
  const initialRef = useRef(initialValues);
  const pinnedRef = useRef(pinned);
  formRef.current = form;
  initialRef.current = initialValues;
  pinnedRef.current = pinned;

  const write = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = undefined;
    if (suppressed.current) return;
    const values = formRef.current.getValues();
    // A composer somebody opened, looked at and closed is not a draft. Storing
    // one anyway would leave the folder page claiming an unfinished prompt for
    // every abandoned click on "PROMPT MỚI" — and typing something and then
    // deleting it back is the same act, so this clears as well as declines to
    // write.
    if (sameForm(values, initialRef.current)) {
      clearPromptDraft(key);
      return;
    }
    writePromptDraft(key, values);
  }, [key]);

  // Restore, once per key. `reset` rather than a field-by-field `setValue`: the
  // form has not been touched yet, so the restored values are its new baseline
  // and `isDirty` should read false against them.
  useEffect(() => {
    if (!enabled) return;
    const stored = readPromptDraft(key);
    if (!stored) return;
    suppressed.current = true;
    formRef.current.reset({ ...initialRef.current, ...stored.values, ...pinnedRef.current });
    suppressed.current = false;
    setRestoredAt(stored.savedAt);
  }, [enabled, key]);

  // Autosave. `form.watch(callback)` fires on every change with the whole form,
  // which is exactly what gets stored — there is no partial write to merge.
  useEffect(() => {
    if (!enabled) return;
    const subscription = formRef.current.watch(() => {
      if (suppressed.current) return;
      clearTimeout(timer.current);
      timer.current = setTimeout(write, DEBOUNCE_MS);
    });
    return () => {
      subscription.unsubscribe();
      // A pending write is the last thing typed, and unmounting is usually a
      // navigation away — the exact moment it is worth keeping. Flushed
      // synchronously rather than dropped with the timer.
      if (timer.current !== undefined) write();
    };
  }, [enabled, write]);

  const acknowledge = useCallback(() => setRestoredAt(undefined), []);

  const clear = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = undefined;
    clearPromptDraft(key);
    setRestoredAt(undefined);
  }, [key]);

  const discard = useCallback(() => {
    suppressed.current = true;
    formRef.current.reset({ ...initialRef.current, ...pinnedRef.current });
    suppressed.current = false;
    clear();
  }, [clear]);

  return { restoredAt, discard, acknowledge, clear };
}

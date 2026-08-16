import { useEffect } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import type { PromptEditorValues } from '@/features/prompt-lifecycle/types';

/**
 * The import screen's half of the agent's UI control.
 *
 * The agent proposes a *form*, not a save: everything it writes here lands in
 * an editable input and stays there until somebody presses the button they
 * would have pressed anyway. That is the whole reason `prefill_form` is a
 * directive rather than a write — the person sees the values before they exist
 * anywhere.
 *
 * The mapping is narrow on purpose. `ALLOWED_FORM_FIELDS` on the server names
 * seven fields; this screen has inputs for five of them, and the two it does not
 * (`purpose`, `tags`) are dropped rather than guessed at. A field the agent can
 * set is a field somebody decided it should be able to set, and `access` is
 * absent from both lists.
 *
 * The prefill is consumed once. Left in place it would re-apply on every render
 * and fight whoever is typing.
 */
export function useAgentImportSurface(form: UseFormReturn<PromptEditorValues>): {
  step: string | null;
  highlight: string | null;
} {
  const { prefill, clearPrefill, step, highlight } = useAgentSurface();

  useEffect(() => {
    if (prefill?.form !== 'import') return;
    const { fields } = prefill;
    const set = (name: keyof PromptEditorValues, value: string) =>
      form.setValue(name, value, { shouldDirty: true, shouldValidate: true });

    if (fields.title) set('title', fields.title);
    if (fields.change_summary) set('changeSummary', fields.change_summary);
    // The name only. `fields.namespace` is read and dropped: the namespace comes
    // from the folder in the URL, it is rendered as a fixed prefix, and A-021
    // makes it permanent — an agent that could change it behind a read-only
    // field would be filing prompts into folders nobody opened.
    if (fields.name) set('name', fields.name);
    if (fields.body) {
      // The agent converts before it prefills, so the body arriving here is
      // already canonical XML. Selecting the import tab would ask the person to
      // re-import something that has been imported.
      set('promptBody', fields.body);
      set('sourceMode', 'authored');
    }
    clearPrefill();
  }, [clearPrefill, form, prefill]);

  return { step, highlight };
}

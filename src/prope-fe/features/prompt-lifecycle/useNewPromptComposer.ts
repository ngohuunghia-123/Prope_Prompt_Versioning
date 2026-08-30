import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import type { BaseSyntheticEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePromptImportFlow } from '@/features/prompt-lifecycle/usePromptImportFlow';
import { usePromptDraft } from '@/features/prompt-lifecycle/usePromptDraft';
import { promptDraftKey } from '@/features/prompt-lifecycle/promptDraftStorage';
import { usePromoteDraftMutation, useUpdateDraftMutation } from '@/features/prompt-lifecycle/queries';
import type { RouterComboEntry } from '@/features/prompt-lifecycle/routerComboTypes';
import type { Revision } from '@/features/prompt-lifecycle/types';
import { promptEditorSchema, type PromptEditorValues } from '@/features/prompt-lifecycle/types';

/** Everything the composer needs to save and promote ONE open draft.
 *
 * Saving writes into the draft in place — a draft is the one editable thing in
 * the version history. Promoting consumes it into the prompt's next version,
 * published immediately, and is gated on the newest version being the
 * published one (requirement 1): the gate is decided by the caller's screen
 * state and re-checked inside `promoteDraft` itself. */
export interface ComposerDraftContext {
  id: string;
  name: string;
  parentRevisionId: string;
  /** The publish gate evaluated for the loaded prompt. */
  canPromote: boolean;
  /** Version number the draft will become when promoted. */
  nextVersion: number;
  /** The prompt's current revisions, for the promote call's gate + numbering. */
  revisions: Revision[];
  /** Copies the chosen combo's frozen rungs at save time — the same thing the
   * registry does server-side when a revision names a combo. Falls back to the
   * draft's own snapshot when the template has vanished (ADR-0069 drift). */
  resolveBinding: (routeComboId: string) => { route: RouterComboEntry[]; routeComboName: string };
}

export interface ComposerDraftFlow {
  name: string;
  nextVersion: number;
  canPromote: boolean;
  save: (event?: BaseSyntheticEvent) => Promise<void>;
  promote: (event?: BaseSyntheticEvent) => Promise<void>;
  saving: boolean;
  promoting: boolean;
  saveError: boolean;
  promoteError: boolean;
}

export function useNewPromptComposer(initialValues: PromptEditorValues, targetPromptId?: string, draftContext?: ComposerDraftContext) {
  const navigate = useNavigate();
  const form = useForm<PromptEditorValues>({ resolver: zodResolver(promptEditorSchema), defaultValues: initialValues });

  // **Recovery is for the create path only.** Registering a prompt is the one
  // screen where ten minutes of typing exists nowhere but this form until the
  // button is pressed. Editing starts from a revision that is already written,
  // so a lost edit loses a change rather than the whole prompt — and a draft
  // held against a prompt whose latest revision has since moved on is a body
  // that would be restored over a newer one without saying so.
  const draft = usePromptDraft(
    form,
    promptDraftKey(initialValues.namespace),
    initialValues,
    // The folder in the URL decides the namespace and A-021 makes it permanent,
    // so it is never taken from storage.
    { namespace: initialValues.namespace },
    targetPromptId === undefined,
  );

  const importFlow = usePromptImportFlow({
    targetPromptId,
    // The prompt exists now, so there is nothing left to recover and a draft
    // left behind would be offered back on a folder that already holds it.
    onSaved: draft.clear,
    // The converted blocks land in the editor and the source is consumed: its
    // text is already recorded as `original_body` in the provenance the flow is
    // holding, so keeping a second copy on the form would only let the two
    // disagree once somebody edits the blocks.
    onConverted: (body) => {
      form.setValue('promptBody', body, { shouldDirty: true, shouldValidate: true });
      form.setValue('sourceText', '', { shouldDirty: true });
      form.setValue('sourceFilename', undefined, { shouldDirty: true });
      form.setValue('sourceFormat', 'txt', { shouldDirty: true });
      form.setValue('sourceMode', 'authored', { shouldDirty: true, shouldValidate: true });
    },
  });

  const updateDraft = useUpdateDraftMutation(targetPromptId ?? '');
  const promoteDraft = usePromoteDraftMutation(targetPromptId ?? '');

  /** The form's binding, shaped the way a draft stores it: a combo names a
   * template whose rungs are copied, a pair binds both fields, never both. */
  const draftValues = (values: PromptEditorValues) => {
    const routed = values.bindingMode === 'combo' && values.routeComboId !== '';
    const binding = routed && draftContext ? draftContext.resolveBinding(values.routeComboId) : undefined;
    return {
      promptBody: values.promptBody,
      providerConfigId: routed ? undefined : values.providerConfigId,
      upstreamModel: routed ? undefined : values.upstreamModel,
      routeComboId: routed ? values.routeComboId : '',
      route: binding?.route ?? [],
      routeComboName: binding?.routeComboName ?? '',
      tags: values.tags,
    };
  };

  const backToDraft = `/app/prompts/${targetPromptId}?tab=content&version=${draftContext?.parentRevisionId ?? ''}&draft=${draftContext?.id ?? ''}`;

  const saveDraft = form.handleSubmit((values) => {
    if (!draftContext || !targetPromptId) return;
    updateDraft.mutate(
      { draftId: draftContext.id, values: draftValues(values) },
      {
        onSuccess: () => {
          void navigate(backToDraft);
        },
      },
    );
  });

  // Promote persists the current edits first — promoting an edited draft that
  // loses the edits would be a version lying about the screen it came from —
  // then consumes the draft into the next version and opens it.
  const promoteDraftAction = form.handleSubmit((values) => {
    if (!draftContext || !targetPromptId) return;
    const run = async () => {
      if (form.formState.isDirty) {
        await updateDraft.mutateAsync({ draftId: draftContext.id, values: draftValues(values) });
      }
      const result = await promoteDraft.mutateAsync({ draftId: draftContext.id, revisions: draftContext.revisions });
      void navigate(`/app/prompts/${targetPromptId}?tab=content&version=${result.revisionId}`);
    };
    void run();
  });

  // "Lưu" no longer saves and leaves. It opens the import flow, which runs
  // the duplicate check first and only writes once the person has answered what
  // it asks — so validation failing here means no request is made at all.
  // A draft edit skips that flow entirely: the draft is the write target.
  const submitImport = form.handleSubmit((values) => {
    if (importFlow.stage === 'review') {
      importFlow.continueAfterReview(values);
      return;
    }
    void importFlow.start(values);
  });

  const evaluate = draftContext ? saveDraft : submitImport;

  const draftFlow: ComposerDraftFlow | undefined = draftContext ? {
    name: draftContext.name,
    nextVersion: draftContext.nextVersion,
    canPromote: draftContext.canPromote,
    save: saveDraft,
    promote: promoteDraftAction,
    saving: updateDraft.isPending,
    promoting: promoteDraft.isPending,
    saveError: updateDraft.isError,
    promoteError: promoteDraft.isError,
  } : undefined;

  return { form, importFlow, draft, evaluate, draftFlow };
}

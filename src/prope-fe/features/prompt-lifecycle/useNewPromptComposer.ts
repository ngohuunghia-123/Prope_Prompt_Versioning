import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { usePromptImportFlow } from '@/features/prompt-lifecycle/usePromptImportFlow';
import { promptEditorSchema, type PromptEditorValues } from '@/features/prompt-lifecycle/types';

export function useNewPromptComposer(initialValues: PromptEditorValues, targetPromptId?: string) {
  const form = useForm<PromptEditorValues>({ resolver: zodResolver(promptEditorSchema), defaultValues: initialValues });

  const importFlow = usePromptImportFlow({
    targetPromptId,
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

  // "Đánh giá" no longer saves and leaves. It opens the import flow, which runs
  // the duplicate check first and only writes once the person has answered what
  // it asks — so validation failing here means no request is made at all.
  const evaluate = form.handleSubmit((values) => {
    if (importFlow.stage === 'review') {
      importFlow.continueAfterReview(values);
      return;
    }
    void importFlow.start(values);
  });

  return { form, importFlow, evaluate };
}

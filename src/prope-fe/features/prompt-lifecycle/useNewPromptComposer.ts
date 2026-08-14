import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useWizardSuggestionMutation } from '@/features/prompt-lifecycle/queries';
import { usePromptImportFlow } from '@/features/prompt-lifecycle/usePromptImportFlow';
import { promptEditorSchema, type PromptEditorValues } from '@/features/prompt-lifecycle/types';

export function useNewPromptComposer(initialValues: PromptEditorValues) {
  const form = useForm<PromptEditorValues>({ resolver: zodResolver(promptEditorSchema), defaultValues: initialValues });
  const suggestionMutation = useWizardSuggestionMutation();
  const importFlow = usePromptImportFlow();

  const generateFromIdea = (idea: string) => {
    suggestionMutation.mutate(
      { intent: idea, context: '', constraints: [], model: form.getValues('providerModel') },
      {
        onSuccess: (suggestions) => {
          const suggestion = suggestions[0];
          if (!suggestion) return;
          const [provider, providerModel] = suggestion.model.split('/');
          form.setValue('title', suggestion.title, { shouldDirty: true, shouldValidate: true });
          form.setValue('modelName', `generated/${suggestion.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}`, { shouldDirty: true, shouldValidate: true });
          form.setValue('provider', provider ?? 'openai', { shouldDirty: true, shouldValidate: true });
          form.setValue('providerModel', providerModel ?? suggestion.model, { shouldDirty: true, shouldValidate: true });
          form.setValue('promptBody', suggestion.promptBody, { shouldDirty: true, shouldValidate: true });
          // The AI wrote canonical XML into `promptBody`, so the screen moves to
          // the tab that shows it. Leaving the import tab selected would put the
          // generated draft behind a tab nobody has a reason to open.
          form.setValue('sourceMode', 'authored', { shouldDirty: true, shouldValidate: true });
        },
      },
    );
  };

  // "Đánh giá" no longer saves and leaves. It opens the import flow, which runs
  // the duplicate check first and only writes once the person has answered what
  // it asks — so validation failing here means no request is made at all.
  const evaluate = form.handleSubmit((values) => { void importFlow.start(values); });

  return { form, generateFromIdea, suggestionMutation, importFlow, evaluate };
}

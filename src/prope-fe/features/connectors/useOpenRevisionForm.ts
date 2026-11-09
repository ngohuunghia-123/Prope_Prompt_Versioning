import { useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getPrompts, getRevisions } from '@/features/connectors/api';
import { revisionTargetSchema } from '@/features/connectors/directContracts';

export function useOpenRevisionForm(initialPromptId = '') {
  const form = useForm<z.infer<typeof revisionTargetSchema>>({ resolver: zodResolver(revisionTargetSchema), defaultValues: { prompt_id: initialPromptId, version_id: '' } });
  const promptId = useWatch({ control: form.control, name: 'prompt_id' });
  const versionId = useWatch({ control: form.control, name: 'version_id' });
  const prompts = useQuery({ queryKey: ['connector', 'prompts'], queryFn: getPrompts });
  const revisions = useQuery({ queryKey: ['connector', 'revisions', promptId], queryFn: () => getRevisions(promptId), enabled: Boolean(promptId) });
  const soleVersionId = revisions.data?.length === 1 ? revisions.data[0]?.version_id : undefined;
  useEffect(() => {
    if (promptId && soleVersionId && !versionId && !revisions.isFetching && !revisions.isError) {
      form.setValue('version_id', soleVersionId, { shouldValidate: true });
    }
  }, [form, promptId, soleVersionId, versionId, revisions.isFetching, revisions.isError]);
  const canOpen = Boolean(promptId && versionId && prompts.data?.some((prompt) => prompt.prompt_id === promptId)
    && revisions.data?.some((revision) => revision.version_id === versionId)
    && !prompts.isFetching && !prompts.isError && !revisions.isFetching && !revisions.isError);
  return { form, promptId, prompts, revisions, canOpen };
}

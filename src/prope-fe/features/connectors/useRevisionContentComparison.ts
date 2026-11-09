import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { getRevision, getRevisions } from '@/features/connectors/api';
import { objectId } from '@/features/connectors/directContracts';

const contentComparisonSchema = z.object({
  before_version_id: objectId, after_version_id: objectId,
  body_kind: z.enum(['canonical', 'original']), only_changed: z.boolean(),
}).refine((value) => value.before_version_id !== value.after_version_id);

export function useRevisionContentComparison(promptId: string, versionId: string) {
  const form = useForm<z.infer<typeof contentComparisonSchema>>({ resolver: zodResolver(contentComparisonSchema),
    defaultValues: { before_version_id: '', after_version_id: versionId, body_kind: 'canonical', only_changed: true } });
  const beforeId = useWatch({ control: form.control, name: 'before_version_id' });
  const afterId = useWatch({ control: form.control, name: 'after_version_id' });
  const bodyKind = useWatch({ control: form.control, name: 'body_kind' });
  const onlyChanged = useWatch({ control: form.control, name: 'only_changed' });
  const revisions = useQuery({ queryKey: ['connector', 'revisions', promptId], queryFn: () => getRevisions(promptId) });
  const defaultBeforeId = revisions.data?.find((revision) => revision.version_id !== afterId)?.version_id;
  useEffect(() => {
    if (!beforeId && defaultBeforeId && !revisions.isError && !revisions.isFetching) form.setValue('before_version_id', defaultBeforeId, { shouldValidate: true });
  }, [form, beforeId, defaultBeforeId, revisions.isError, revisions.isFetching]);
  const validPair = Boolean(!revisions.isError && !revisions.isPending && beforeId !== afterId
    && revisions.data?.some((revision) => revision.version_id === beforeId)
    && revisions.data.some((revision) => revision.version_id === afterId));
  const before = useQuery({ queryKey: ['connector', 'revision', beforeId], queryFn: () => getRevision(beforeId), enabled: validPair });
  const after = useQuery({ queryKey: ['connector', 'revision', afterId], queryFn: () => getRevision(afterId), enabled: validPair });
  const matches = Boolean(before.data?.prompt_id === promptId && after.data?.prompt_id === promptId
    && before.data?.version_id === beforeId && after.data?.version_id === afterId);
  const ready = validPair && matches && !before.isError && !after.isError;
  const beforeBody = bodyKind === 'original' ? before.data?.original_body : before.data?.body;
  const afterBody = bodyKind === 'original' ? after.data?.original_body : after.data?.body;
  return { form, revisions, before, after, beforeId, afterId, bodyKind, onlyChanged, ready,
    invalidTarget: validPair && before.isSuccess && after.isSuccess && !matches,
    loading: revisions.isPending || (validPair && (before.isPending || after.isPending)), beforeBody, afterBody };
}

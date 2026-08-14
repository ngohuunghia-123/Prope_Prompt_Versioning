import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { previewPromptIndex } from '@/features/prompt-lifecycle/api';
import {
  lifecycleKeys,
  promptIndexJobOptions,
  promptIndexOptions,
  useDeletePromptIndexMutation,
  useTriggerPromptIndexMutation,
} from '@/features/prompt-lifecycle/queries';

export function usePromptIndexing(workspaceId: string, promptId: string) {
  const client = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [jobId, setJobId] = useState('');
  const status = useQuery({
    ...promptIndexOptions(workspaceId, promptId),
    enabled: Boolean(workspaceId && promptId),
  });
  const preview = useQuery({
    queryKey: [...lifecycleKeys.promptIndex(workspaceId, promptId), 'preview'],
    queryFn: () => previewPromptIndex(promptId),
    enabled: previewOpen,
    staleTime: 0,
  });
  const trigger = useTriggerPromptIndexMutation(workspaceId, promptId);
  const remove = useDeletePromptIndexMutation(workspaceId, promptId);
  const job = useQuery({
    ...promptIndexJobOptions(workspaceId, jobId),
    enabled: Boolean(jobId),
  });
  const start = useMutation({
    mutationFn: () => trigger.mutateAsync(),
    onSuccess: ({ job_id }) => {
      setJobId(job_id);
      setPreviewOpen(false);
    },
  });

  useEffect(() => {
    if (job.data?.status === 'completed' || job.data?.status === 'failed') {
      void client.invalidateQueries({
        queryKey: lifecycleKeys.promptIndex(workspaceId, promptId),
      });
    }
  }, [client, job.data?.status, promptId, workspaceId]);

  return { status, preview, previewOpen, setPreviewOpen, start, remove, job };
}

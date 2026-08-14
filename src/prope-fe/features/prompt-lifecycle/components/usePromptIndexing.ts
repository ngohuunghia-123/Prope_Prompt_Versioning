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

export function usePromptIndexing(promptId: string) {
  const client = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [jobId, setJobId] = useState('');
  const status = useQuery({
    ...promptIndexOptions(promptId),
    enabled: Boolean(promptId),
  });
  const preview = useQuery({
    queryKey: [...lifecycleKeys.promptIndex(promptId), 'preview'],
    queryFn: () => previewPromptIndex(promptId),
    enabled: previewOpen,
    staleTime: 0,
  });
  const trigger = useTriggerPromptIndexMutation(promptId);
  const remove = useDeletePromptIndexMutation(promptId);
  const job = useQuery({
    ...promptIndexJobOptions(jobId),
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
        queryKey: lifecycleKeys.promptIndex(promptId),
      });
    }
  }, [client, job.data?.status, promptId]);

  return { status, preview, previewOpen, setPreviewOpen, start, remove, job };
}

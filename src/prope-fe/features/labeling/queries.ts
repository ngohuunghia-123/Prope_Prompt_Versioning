import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { getLabelingQueue, saveCallLabel } from '@/features/labeling/api';
import type { CallLabel } from '@/features/labeling/types';

const KEY = ['labeling', 'queue'] as const;

export const labelingQueueOptions = queryOptions({ queryKey: KEY, queryFn: getLabelingQueue, staleTime: 15_000 });

export function useSaveCallLabelMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ promptId, callId, label }: { promptId: string; callId: string; label: CallLabel }) => saveCallLabel(promptId, callId, label),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

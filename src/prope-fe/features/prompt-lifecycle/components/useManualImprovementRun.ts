import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { listManualImprovementRuns, startManualImprovement } from '@/features/prompt-lifecycle/manualImprovementApi';

export function useManualImprovementRun(promptId: string) {
  const client = useQueryClient();
  const queryKey = ['manual-improvement', promptId];
  const query = useQuery({
    queryKey,
    queryFn: () => listManualImprovementRuns(promptId),
    refetchInterval: (current) => current.state.data?.[0] && ['queued', 'running'].includes(current.state.data[0].status) ? 2_000 : false,
    staleTime: 1_000,
  });
  const start = useMutation({
    mutationFn: (versionId: string) => startManualImprovement(promptId, versionId),
    onSuccess: (run) => client.setQueryData(queryKey, (current: typeof query.data) => [run, ...(current ?? []).filter((item) => item.run_id !== run.run_id)]),
  });
  return { query, run: query.data?.[0], start };
}

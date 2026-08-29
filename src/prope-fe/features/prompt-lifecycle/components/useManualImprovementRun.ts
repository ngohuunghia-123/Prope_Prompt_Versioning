import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { listManualImprovementRuns, startManualImprovement } from '@/features/prompt-lifecycle/manualImprovementApi';
import { lifecycleKeys } from '@/features/prompt-lifecycle/queries';

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
    mutationFn: ({ versionId, evidenceSource }: { versionId: string; evidenceSource?: 'production' | 'eval_analysis' }) =>
      startManualImprovement(promptId, versionId, evidenceSource ?? 'production'),
    onSuccess: (run) => client.setQueryData(queryKey, (current: typeof query.data) => [run, ...(current ?? []).filter((item) => item.run_id !== run.run_id)]),
  });
  const run = query.data?.[0];
  useEffect(() => {
    if (!run || ['queued', 'running'].includes(run.status)) return;
    void client.invalidateQueries({ queryKey: lifecycleKeys.promptFindings(promptId) });
    void client.invalidateQueries({ queryKey: lifecycleKeys.improvementInbox });
  }, [client, promptId, run]);
  return { query, run, start };
}

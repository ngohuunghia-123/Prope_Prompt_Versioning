import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import { createAgentDraft } from '@/features/prompt-lifecycle/draftApi';
import { listManualImprovementRuns, startManualImprovement } from '@/features/prompt-lifecycle/manualImprovementApi';
import { lifecycleKeys } from '@/features/prompt-lifecycle/queries';

export function useManualImprovementRun(promptId: string) {
  const { t } = useTranslation();
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
    const action = run.result_actions[0];
    const versionId = run.version_id;
    const candidateBody = action?.candidate_body;
    // The gated candidate lands as a draft UNDER the version the run targeted
    // (never a new version): the draft is idempotent per run, so every hook
    // instance watching this run parks the same draft. Creation is
    // session-local, so refetch the prompt afterwards for the rail to show it.
    if (action?.drafted === 'true' && versionId && candidateBody) {
      void createAgentDraft({
        promptId,
        runId: run.run_id,
        parentRevisionId: versionId,
        promptBody: candidateBody,
        summary: t('lifecycle.promptDetail.improvementTrust.agentDraftSummary'),
      }).then(() => client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) }));
    }
    void client.invalidateQueries({ queryKey: lifecycleKeys.promptFindings(promptId) });
    void client.invalidateQueries({ queryKey: lifecycleKeys.improvementInbox });
    void client.invalidateQueries({ queryKey: lifecycleKeys.prompt(promptId) });
  }, [client, promptId, run, t]);
  return { query, run, start };
}

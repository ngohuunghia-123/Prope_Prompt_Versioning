import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest } from '@/lib/apiClient';
import { isUncertainWrite } from '@/features/connectors/writeOutcome';
import { agentRunSchema } from '@/features/floating-agent/types';
import { callHost } from '@/features/connectors/bridge';

export function useConnectorImprovement(promptId: string, versionId: string) {
  const client = useQueryClient(); const [selected, setSelected] = useState('');
  const history = useQuery({ queryKey: ['connector', 'improvementHistory', promptId, versionId],
    queryFn: async () => (await apiRequest('/api/v1/agent-runs?limit=100', { schema: z.array(agentRunSchema) }))
      .filter((run) => run.kind === 'improvement' && run.prompt_id === promptId && run.version_id === versionId) });
  const runId = selected || history.data?.[0]?.run_id || '';
  const run = useQuery({ queryKey: ['connector', 'improvement', runId], enabled: Boolean(runId),
    queryFn: () => apiRequest(`/api/v1/agent-runs/${encodeURIComponent(runId)}`, { schema: agentRunSchema }),
    refetchInterval: (query) => query.state.error || (query.state.data && !['queued', 'running'].includes(query.state.data.status)) ? false : 3000 });
  const start = useMutation({ mutationFn: (evalRunId: string) => callHost('start_improvement', { prompt_id: promptId, version_id: versionId, eval_run_id: evalRunId }),
    onSuccess: (value) => { setSelected(agentRunSchema.parse(value).run_id); void client.invalidateQueries(); } });
  const review = useMutation({ mutationFn: () => callHost('review_improvement', { prompt_id: promptId, version_id: versionId, run_id: runId }) });
  const uncertain = isUncertainWrite(start.error);
  return { history, run, runId, start, review, setSelected, uncertain };
}

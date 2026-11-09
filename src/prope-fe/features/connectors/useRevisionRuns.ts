import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { isUncertainWrite } from '@/features/connectors/writeOutcome';
import { callHost } from '@/features/connectors/bridge';
import { getPromptEvalRuns } from '@/features/prompt-lifecycle/insightsApi';

export function useRevisionRuns(promptId: string, versionId: string) {
  const client = useQueryClient(); const [selected, setSelected] = useState('');
  const history = useQuery({ queryKey: ['connector', 'runs', promptId, versionId], queryFn: () => getPromptEvalRuns(promptId, versionId),
    refetchInterval: (query) => query.state.data?.some((run) => ['queued', 'running'].includes(run.status)) ? 3000 : false });
  const start = useMutation({ mutationFn: () => callHost('run_revision', { prompt_id: promptId, version_id: versionId }), onSuccess: () => client.invalidateQueries() });
  const runId = selected || history.data?.[0]?.run_id || '';
  const uncertain = isUncertainWrite(start.error);
  return { history, start, runId, setSelected, uncertain };
}

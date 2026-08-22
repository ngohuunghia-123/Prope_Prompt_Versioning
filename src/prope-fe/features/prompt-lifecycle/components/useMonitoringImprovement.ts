import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { acceptProposal, dismissFinding, dismissProposal, getPromptFindings } from '@/features/prompt-lifecycle/improvementApi';
import { lifecycleKeys, promptCallRecordsOptions, promptUsageOptions } from '@/features/prompt-lifecycle/queries';

export function useMonitoringImprovement(promptId: string, onOpenEditor: (body: string, findingId: string) => void) {
  const client = useQueryClient();
  const usage = useQuery(promptUsageOptions(promptId, '7d', 'gateway'));
  const calls = useQuery(promptCallRecordsOptions({ promptId, source: 'gateway', limit: 3 }));
  const findings = useQuery({ queryKey: lifecycleKeys.promptFindings(promptId), queryFn: () => getPromptFindings(promptId), staleTime: 30_000 });
  const invalidate = () => {
    void client.invalidateQueries({ queryKey: lifecycleKeys.promptFindings(promptId) });
    void client.invalidateQueries({ queryKey: lifecycleKeys.improvementInbox });
    void client.invalidateQueries({ queryKey: ['lifecycle', 'summary', promptId] });
  };
  const dismissOne = useMutation({ mutationFn: ({ findingId, reason }: { findingId: string; reason: string }) => dismissFinding(findingId, reason), onSuccess: invalidate });
  const accept = useMutation({
    mutationFn: ({ proposalId }: { proposalId: string; findingId: string }) => acceptProposal(proposalId),
    onSuccess: (result, variables) => { invalidate(); if (result.candidate_body) onOpenEditor(result.candidate_body, variables.findingId); },
  });
  const refuse = useMutation({ mutationFn: ({ proposalId, reason }: { proposalId: string; reason: string }) => dismissProposal(proposalId, reason), onSuccess: invalidate });
  const acceptProposalForFinding = async (proposalId: string) => {
    const findingId = findings.data?.find((item) => item.proposal?.proposal_id === proposalId)?.finding_id;
    if (findingId) await accept.mutateAsync({ proposalId, findingId });
  };
  return { usage, calls, findings, busy: dismissOne.isPending || accept.isPending || refuse.isPending, dismissOne, acceptProposalForFinding, refuse };
}

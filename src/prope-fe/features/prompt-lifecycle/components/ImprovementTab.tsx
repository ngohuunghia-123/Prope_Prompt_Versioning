import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { ImprovementFindingList } from '@/features/prompt-lifecycle/components/ImprovementFindingList';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import {
  acceptProposal,
  dismissFinding,
  dismissProposal,
  getPromptFindings,
} from '@/features/prompt-lifecycle/improvementApi';
import { lifecycleKeys } from '@/features/prompt-lifecycle/queries';

interface ImprovementTabProps {
  promptId: string;
  /** Where to send somebody who accepts a proposal. The write is theirs to make. */
  onOpenEditor?: (candidateBody: string) => void;
}

/**
 * One prompt's degradation history. INT-046, beside ADR-0055's call-records tab.
 *
 * **Shows dismissed and resolved findings as well as open ones**, unlike the
 * inbox. The inbox is a queue and shows what is outstanding; this is the prompt's
 * own record, and a reader who opened it asked for the whole of it.
 *
 * **An empty tab is the healthy state.** A-162's inversion, reused from ADR-0064:
 * the sweep writes nothing when nothing is wrong, so no findings means the last
 * pass looked and found the prompt behaving. The copy says that rather than
 * apologising for missing data.
 *
 * **Accepting a proposal navigates; it does not save.** `acceptProposal` records
 * the disposition and returns a candidate body — the revision is written by
 * prompt-registry on a separate, explicit request the person makes (SR-6,
 * ADR-0066). `onOpenEditor` is how that hand-off happens, and a call site that
 * omits it gets a disposition recorded and no editor, which is a visible gap
 * rather than a silent write.
 */
export function ImprovementTab({ promptId, onOpenEditor }: ImprovementTabProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: lifecycleKeys.promptFindings(promptId),
    queryFn: () => getPromptFindings(promptId),
    staleTime: 30_000,
  });

  const invalidate = () => {
    void client.invalidateQueries({ queryKey: lifecycleKeys.promptFindings(promptId) });
    void client.invalidateQueries({ queryKey: lifecycleKeys.improvementInbox });
  };

  const dismissOne = useMutation({
    mutationFn: ({ findingId, reason }: { findingId: string; reason: string }) =>
      dismissFinding(findingId, reason),
    onSuccess: invalidate,
  });

  const accept = useMutation({
    mutationFn: (proposalId: string) => acceptProposal(proposalId),
    onSuccess: (result) => {
      invalidate();
      if (result.candidate_body) onOpenEditor?.(result.candidate_body);
    },
  });

  const refuse = useMutation({
    mutationFn: ({ proposalId, reason }: { proposalId: string; reason: string }) =>
      dismissProposal(proposalId, reason),
    onSuccess: invalidate,
  });

  if (query.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  if (query.data.length === 0) {
    return (
      <div className="p-6 text-center">
        <p className="text-sm text-fg">{t('improvement.inbox.empty')}</p>
        <p className="mt-1 text-xs text-fg-muted">{t('improvement.inbox.emptyHint')}</p>
      </div>
    );
  }

  return (
    <ImprovementFindingList
      findings={query.data}
      busy={dismissOne.isPending || accept.isPending || refuse.isPending}
      onDismissFinding={async (findingId, reason) => {
        await dismissOne.mutateAsync({ findingId, reason });
      }}
      onAcceptProposal={async (proposalId) => {
        await accept.mutateAsync(proposalId);
      }}
      onDismissProposal={async (proposalId, reason) => {
        await refuse.mutateAsync({ proposalId, reason });
      }}
    />
  );
}

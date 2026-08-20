import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { ImprovementFindingList } from '@/features/prompt-lifecycle/components/ImprovementFindingList';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import {
  acceptProposal,
  dismissFinding,
  dismissProposal,
  getInbox,
} from '@/features/prompt-lifecycle/improvementApi';
import { lifecycleKeys } from '@/features/prompt-lifecycle/queries';

/**
 * The findings inbox. INT-045.
 *
 * **An empty inbox is the success condition**, and the screen says so rather than
 * apologising for having no data. A-162's inversion, reused from ADR-0064: the
 * sweep writes nothing when nothing is wrong, so an empty list means the last
 * pass looked at every released prompt in the workspace and found them all
 * behaving.
 *
 * **A prompt this reader cannot see contributes nothing to this screen** — no
 * row, no count, and no total that differs from a workspace where nothing is
 * wrong (SR-7). That is enforced on the server, per prompt, before any finding is
 * read; there is no client-side filter here and there must not be one, because a
 * filter on this side would mean the data reached the browser first.
 *
 * **Accepting a proposal navigates to the editor and saves nothing** (SR-6). The
 * route records the disposition and hands back a candidate body; the revision is
 * written by prompt-registry on the person's own second, explicit act.
 */
export function ImprovementInboxPage() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const navigate = useNavigate();

  const query = useQuery({
    queryKey: lifecycleKeys.improvementInbox,
    queryFn: getInbox,
    staleTime: 30_000,
  });

  const invalidate = () => {
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
      // The editor, not a save. `candidate_body` is carried in navigation state so
      // the editor can prefill it without a second fetch — and so that a person
      // who navigates away has applied nothing.
      navigate(`/app/prompts/${result.prompt_id}/edit`, {
        state: { candidateBody: result.candidate_body },
      });
    },
  });

  const refuse = useMutation({
    mutationFn: ({ proposalId, reason }: { proposalId: string; reason: string }) =>
      dismissProposal(proposalId, reason),
    onSuccess: invalidate,
  });

  return (
    <div className="grid gap-6">
      <PageIntro title={t('improvement.inbox.title')} description={t('improvement.inbox.subtitle')} />

      <div className="bg-surface">
        {query.isPending ? (
          <QueryState state="loading" loadingLayout="table" />
        ) : query.isError ? (
          <QueryState state="error" onRetry={() => void query.refetch()} />
        ) : query.data.total === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-fg">{t('improvement.inbox.empty')}</p>
            <p className="mt-1 text-xs text-fg-muted">{t('improvement.inbox.emptyHint')}</p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-4 border-b border-border p-4 text-sm text-fg-muted sm:p-6">
              <span>{t('improvement.inbox.warnings', { count: query.data.warning_count })}</span>
              <span>{t('improvement.inbox.advice', { count: query.data.advice_count })}</span>
            </div>
            <ImprovementFindingList
              findings={query.data.findings}
              showPromptId
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
          </>
        )}
      </div>
    </div>
  );
}

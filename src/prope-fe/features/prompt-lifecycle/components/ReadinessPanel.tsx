import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Notification } from '@/components/Notification';
import { ReadinessCard } from '@/features/prompt-lifecycle/components/ReadinessCard';
import { UsageProfileFields } from '@/features/prompt-lifecycle/components/UsageProfileFields';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import {
  declareUsageProfileAxis,
  dismissFinding,
  getReadinessCard,
  startProbe,
  type ReadinessTrigger,
} from '@/features/prompt-lifecycle/readinessApi';
import type { UsageProfileAxis } from '@/features/prompt-lifecycle/readinessTypes';
import { isApiError } from '@/lib/apiClient';

/**
 * The readiness card with its own query, mounted beside a revision.
 *
 * **This component owns the fetch so the card component stays pure**, which is
 * what lets the card be rendered from a frozen report, from a live draft, or
 * from a test fixture without three code paths.
 *
 * **The refusal codes are rendered from the catalogue, not from the message.**
 * A probe refuses with `spend_ceiling_reached`, `no_applicable_sets` or
 * `revision_has_no_binding`, and ADR-0053 means the client renders the code. An
 * unrecognised one falls back to the generic error state rather than printing an
 * English sentence from the server at somebody.
 *
 * **Nothing here can block anything.** A failed fetch renders as a panel that is
 * down; it never prevents a save, a submit or a release, because the module it
 * talks to has no gate in it (ADR-0067 §4) and a client that behaved as though it
 * did would be inventing one.
 *
 * **The four declarations sit above the card rather than on a settings page**,
 * because the card's own `profile_undeclared` finding says *declare what this is
 * for* and an action a reader has to go looking for is an action most of them
 * will not take. Editing one re-fetches, so the effect of a declaration is the
 * findings visibly changing — which is the differentiator demonstrating itself
 * rather than being explained.
 *
 * **`canDeclare` defaults to true because the server is the authority.** This
 * SPA carries no permission model — every edit control renders and the route
 * refuses the ones the actor may not use, which is the only arrangement where a
 * stale client cannot grant anything. The prop exists for the surfaces that
 * already know they are read-only, such as a reviewer looking at a frozen
 * report, where offering an edit would be a promise the next click breaks.
 */

export interface ReadinessPanelProps {
  promptId: string;
  versionId: string;
  trigger?: ReadinessTrigger;
  /** Offer the four declarations. Defaults to true; the route enforces `prompt.edit`. */
  canDeclare?: boolean;
  className?: string;
}

const READINESS_KEY = 'readiness';

export function ReadinessPanel({
  promptId,
  versionId,
  trigger = 'edit',
  canDeclare = true,
  className,
}: ReadinessPanelProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const queryKey = [READINESS_KEY, promptId, versionId, trigger];

  const query = useQuery({
    queryKey,
    queryFn: () => getReadinessCard(promptId, versionId, trigger),
    enabled: Boolean(promptId && versionId),
    // Short, because Lane A is recomputed on every read and an author editing a
    // draft expects the panel to follow them. A frozen report is immutable, so
    // re-reading one costs a round trip and can never change the answer.
    staleTime: 15_000,
  });

  const invalidate = () => client.invalidateQueries({ queryKey });

  const dismissal = useMutation({
    mutationFn: ({ ruleId, reason }: { ruleId: string; reason: string }) =>
      dismissFinding(promptId, ruleId, reason),
    onSuccess: invalidate,
  });

  const probe = useMutation({
    mutationFn: () => startProbe(promptId, versionId),
    onSuccess: invalidate,
  });

  const declaration = useMutation({
    mutationFn: ({ axis, value }: { axis: UsageProfileAxis; value: string }) =>
      declareUsageProfileAxis(promptId, axis, value),
    // Every rule is filtered against this profile, so a declaration changes the
    // whole card and not one row of it.
    onSuccess: invalidate,
  });

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;

  return (
    <div className={className}>
      {canDeclare ? (
        <UsageProfileFields
          profile={query.data.profile}
          disabled={declaration.isPending}
          onChange={(axis, value) => void declaration.mutateAsync({ axis, value })}
          className="mb-6"
        />
      ) : null}
      {declaration.isError ? (
        <Notification tone="error" title={t('common.tryAgain')}>
          {t('readiness.profile.title')}
        </Notification>
      ) : null}
      {probe.isError ? <ProbeRefusal error={probe.error} /> : null}
      <ReadinessCard
        card={query.data}
        probeBusy={probe.isPending}
        onDismiss={(ruleId, reason) => dismissal.mutateAsync({ ruleId, reason })}
        onStartProbe={async () => {
          // The run's counts arrive on the refetched card, so the result is
          // deliberately dropped here rather than threaded through the prop.
          await probe.mutateAsync();
        }}
      />
      {dismissal.isError ? (
        <Notification tone="error" title={t('common.tryAgain')}>
          {t('readiness.card.dismissReasonRequired')}
        </Notification>
      ) : null}
    </div>
  );
}

/** The three named refusals, each with a key. Anything else is a generic failure. */
function ProbeRefusal({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const code = isApiError(error) ? error.message : '';
  const known = ['spend_ceiling_reached', 'no_applicable_sets', 'revision_has_no_binding'];
  return (
    <Notification tone="warning" title={t('readiness.probe.title')}>
      {known.includes(code) ? t(`readiness.probe.refusal.${code}`) : t('common.tryAgain')}
    </Notification>
  );
}

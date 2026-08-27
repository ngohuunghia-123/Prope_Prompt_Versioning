import { useTranslation } from 'react-i18next';
import { RouterComboSummary } from '@/features/prompt-lifecycle/components/RouterComboSummary';
import type { Revision } from '@/features/prompt-lifecycle/types';
import { useProviderName } from '@/features/prompt-lifecycle/useProviderName';

/**
 * What one revision binds to, read from that revision — ADR-0069.
 *
 * Three surfaces render this and they were each rendering it slightly
 * differently from `prompt.provider`, which is the **latest** revision's
 * binding whichever revision is on screen. Browsing an older revision already
 * showed the wrong provider before routing existed; per-revision route
 * snapshots make that a bug that cannot be left alone, because the route IS the
 * revision by construction.
 *
 * A routed revision shows its rungs in order, and shows them **frozen**: no
 * "this provider is disabled" warning, because that revision was approved
 * against exactly these rungs and a badge inviting somebody to fix it is a
 * badge inviting somebody to edit a record that does not change.
 */
export function RevisionBindingDisplay({ revision, snapshotNote = false, className }: {
  revision: Revision;
  /**
   * Say, in one line, that these rungs are a COPY taken when the revision was
   * created. For a reviewer this is the difference between approving a route
   * and approving a pointer at a template somebody can edit afterwards — and
   * the whole approval record rests on it being the former.
   */
  snapshotNote?: boolean;
  className?: string;
}) {
  const { t } = useTranslation();
  const providerName = useProviderName(revision.providerConfigId);

  if (revision.route.length > 0) {
    return (
      <div className={className}>
        <p className="text-body font-medium text-ink">
          {revision.routeComboName || t('lifecycle.router.unnamedCombo')}
        </p>
        <RouterComboSummary entries={revision.route} warnUnusable={false} className="mt-1" />
        {snapshotNote ? (
          <p className="mt-1 text-caption text-muted">{t('lifecycle.router.snapshot.frozen')}</p>
        ) : null}
      </div>
    );
  }

  if (providerName && revision.upstreamModel) {
    return (
      <p className={className}>
        <span className="text-body font-medium text-ink">{providerName}</span>
        <span aria-hidden className="px-1 text-muted">·</span>
        <span className="font-mono text-body text-ink">{revision.upstreamModel}</span>
      </p>
    );
  }

  return <p className={className}>{t('lifecycle.promptDetail.noBinding')}</p>;
}

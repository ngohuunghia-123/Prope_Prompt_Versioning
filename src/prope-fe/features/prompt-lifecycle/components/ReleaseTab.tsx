import { useTranslation } from 'react-i18next';

import { StatusBadge } from '@/components/StatusBadge';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { ReleaseEvidence } from '@/features/prompt-lifecycle/components/ReleaseEvidence';
import { ReleaseGate } from '@/features/prompt-lifecycle/components/ReleaseGate';
import { ReleaseHistoryTable } from '@/features/prompt-lifecycle/components/ReleaseHistoryTable';
import { useReleaseControl } from '@/features/prompt-lifecycle/useReleaseControl';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';

interface ReleaseTabProps {
  prompt: PromptDetail;
  /** The revision selected in the rail — the tab acts on that one, not on the newest. */
  versionId: string;
  revisionLabel: string;
  revisionLabels: Record<string, string>;
}

/**
 * The path from a draft to production, for one revision at a time.
 *
 * **This is the screen the product exists for.** No prompt reaches production
 * without a recorded human approval, and this is where that approval is
 * recorded — so every act here writes a history row, and none of them can be
 * undone by deleting one.
 *
 * The rail on the left still selects the revision. A reader comparing two
 * revisions moves between them there and this tab follows, which is why the
 * review screen is keyed by version rather than by prompt.
 */
export function ReleaseTab({ prompt, versionId, revisionLabel, revisionLabels }: ReleaseTabProps) {
  const { t } = useTranslation();
  const control = useReleaseControl(prompt.id, versionId);
  const screen = control.screen.data;
  const releasedLabel = screen?.released_version_id
    ? revisionLabels[screen.released_version_id] ?? screen.released_version_id
    : null;

  if (control.screen.isPending) return <QueryState state="loading" />;
  if (control.screen.isError) return <QueryState state="error" onRetry={() => void control.screen.refetch()} />;
  if (!screen) return <QueryState state="empty" />;

  return (
    <div className="grid gap-6">
      {/* What is live right now, named by the handle a consuming product calls.
          This is the answer to "is this prompt in production", and it belongs
          above the decision rather than inside it. */}
      <section className="rounded-modal border border-border bg-surface p-5 shadow-panel" aria-labelledby="release-current-title">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 id="release-current-title" className="font-display text-heading-3 text-ink">
              {t('lifecycle.release.currentTitle')}
            </h2>
            <p className="mt-2 text-body text-muted">
              {releasedLabel
                ? t('lifecycle.release.currentReleased', { revision: releasedLabel })
                : t('lifecycle.release.currentNone')}
            </p>
          </div>
          <StatusBadge tone={screen.released_version_id ? 'active' : 'disabled'}>
            {screen.released_version_id ? t('status.inUse') : t('lifecycle.release.notPublished')}
          </StatusBadge>
        </div>
        <dl className="mt-4 grid gap-x-8 gap-y-3 border-t border-border pt-4 sm:grid-cols-2">
          <div>
            <dt className="text-caption text-muted">{t('lifecycle.release.modelName')}</dt>
            <dd className="mt-1 font-mono text-body text-ink">{screen.model_name}</dd>
          </div>
          <div>
            <dt className="text-caption text-muted">{t('lifecycle.release.latestRevision')}</dt>
            <dd className="mt-1 text-body text-ink">{screen.latest_revision_number}</dd>
          </div>
        </dl>
      </section>

      <ReleaseGate screen={screen} control={control} revisionLabel={revisionLabel} />

      <ReleaseEvidence screen={screen} />

      {control.history.isError ? (
        <QueryState state="error" onRetry={() => void control.history.refetch()} />
      ) : (
        <ReleaseHistoryTable releases={control.history.data ?? []} revisionLabels={revisionLabels} />
      )}
    </div>
  );
}

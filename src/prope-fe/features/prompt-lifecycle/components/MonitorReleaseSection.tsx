import { ClockCounterClockwise, FileText } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { ReleaseEvidence } from '@/features/prompt-lifecycle/components/ReleaseEvidence';
import { ReleaseGate } from '@/features/prompt-lifecycle/components/ReleaseGate';
import { ReleaseHistoryTable } from '@/features/prompt-lifecycle/components/ReleaseHistoryTable';
import { useReleaseControl } from '@/features/prompt-lifecycle/useReleaseControl';

interface MonitorReleaseSectionProps {
  promptId: string;
  versionId: string;
  revisionLabel: string;
  revisionLabels: Record<string, string>;
  releasedVersionId: string | null;
}

function revisionStatusKey(status: string) {
  if (status === 'Draft') return 'draft';
  if (status === 'In review') return 'inReview';
  if (status === 'Approved') return 'approved';
  return undefined;
}

/**
 * The release state, folded into Monitor & Improve.
 *
 * The old standalone "Put into use" tab became this section: the same status
 * strip and the same one-available-act gate, without its own page heading —
 * the tab heading above it already says where the reader is.
 */
export function MonitorReleaseSection({ promptId, versionId, revisionLabel, revisionLabels, releasedVersionId }: MonitorReleaseSectionProps) {
  const { t } = useTranslation();
  const [drawer, setDrawer] = useState<'evidence' | 'history'>();
  const control = useReleaseControl(promptId, versionId);
  const screen = control.screen.data;
  if (control.screen.isPending) return <QueryState state="loading" />;
  if (control.screen.isError) return <QueryState state="error" onRetry={() => void control.screen.refetch()} />;
  if (!screen) return <QueryState state="empty" />;
  const releasedLabel = screen.released_version_id ? revisionLabels[screen.released_version_id] ?? screen.released_version_id : null;
  const suites = screen.summary?.suites ?? [];
  const passed = suites.reduce((total, suite) => total + suite.pass_count, 0);
  const failed = suites.reduce((total, suite) => total + suite.fail_count + suite.error_count, 0);
  const statusKey = revisionStatusKey(screen.revision.status);

  return (
    <section className="rounded-modal border border-border bg-surface shadow-panel" aria-labelledby="monitor-release-heading">
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div>
          <h2 id="monitor-release-heading" className="font-display text-heading-3 text-ink">{t('lifecycle.surface.release.title')}</h2>
          <p className="mt-1 text-body text-muted">{t('lifecycle.surface.release.description')}</p>
        </div>
        <StatusBadge tone={releasedVersionId ? 'active' : 'disabled'}>{releasedVersionId ? t('status.inUse') : t('lifecycle.release.notPublished')}</StatusBadge>
      </div>
      <dl className="grid gap-3 px-5 pb-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.release.live')}</dt><dd className="mt-1 text-body font-semibold text-ink">{releasedLabel ?? t('lifecycle.surface.release.none')}</dd></div>
        <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.release.viewing')}</dt><dd className="mt-1 text-body font-semibold text-ink">{revisionLabel}</dd></div>
        <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.release.eval')}</dt><dd className="mt-1 text-body font-semibold text-ink">{screen.summary_available ? t('lifecycle.surface.release.evalCounts', { passed, failed }) : t('lifecycle.surface.release.unknown')}</dd></div>
        <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.release.approval')}</dt><dd className="mt-1 text-body font-semibold text-ink">{statusKey ? t(`lifecycle.status.${statusKey}`) : t('lifecycle.surface.release.unknown')}</dd></div>
      </dl>
      <ReleaseGate screen={screen} control={control} revisionLabel={revisionLabel} />
      <div className="flex flex-wrap gap-2 p-5 pt-0">
        <Button type="button" intent="ghost" size="small" leadingIcon={<FileText aria-hidden className="size-4" />} onClick={() => setDrawer('evidence')}>{t('lifecycle.surface.release.evidence')}</Button>
        <Button type="button" intent="ghost" size="small" leadingIcon={<ClockCounterClockwise aria-hidden className="size-4" />} onClick={() => setDrawer('history')}>{t('lifecycle.surface.release.history')}</Button>
      </div>
      <Drawer open={drawer === 'evidence'} onClose={() => setDrawer(undefined)} side="right" size="wide" title={t('lifecycle.surface.release.evidence')}><div className="h-full overflow-y-auto"><ReleaseEvidence screen={screen} /></div></Drawer>
      <Drawer open={drawer === 'history'} onClose={() => setDrawer(undefined)} side="right" size="wide" title={t('lifecycle.surface.release.history')}><div className="h-full overflow-y-auto">{control.history.isError ? <QueryState state="error" onRetry={() => void control.history.refetch()} /> : <ReleaseHistoryTable releases={control.history.data ?? []} revisionLabels={revisionLabels} />}</div></Drawer>
    </section>
  );
}

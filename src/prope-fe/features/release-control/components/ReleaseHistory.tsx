import { ClockCounterClockwise, RocketLaunch } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import type { ReleaseWorkspace } from '@/features/release-control/types';

interface ReleaseHistoryProps { workspace: ReleaseWorkspace; }

export function ReleaseHistory({ workspace }: ReleaseHistoryProps) {
  const { t, i18n } = useTranslation();
  return <section className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><div className="flex items-center gap-3"><ClockCounterClockwise aria-hidden className="size-6 text-secondary" /><div><p className="text-overline font-semibold text-muted">{t('release.history.eyebrow')}</p><h2 className="mt-1 text-heading-2 font-semibold">{t('release.history.title')}</h2></div></div><ol className="mt-5 space-y-3">{workspace.releases.map((record) => { const date = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(record.releasedAt)); return <li key={record.id} className="flex flex-col gap-3 rounded-modal border border-border bg-canvas p-4 sm:flex-row sm:items-center"><span className="grid size-10 shrink-0 place-items-center rounded-full bg-secondary text-inverse"><RocketLaunch aria-hidden className="size-5" /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-body font-semibold text-ink">{t('revisions.version', { number: record.revisionNumber })}</p><StatusBadge tone={record.kind === 'breakGlass' ? 'error' : 'disabled'}>{t(`release.history.kind.${record.kind}`)}</StatusBadge>{record.current ? <StatusBadge tone="active">{t('release.status.inUse')}</StatusBadge> : null}</div><p className="mt-1 break-all text-caption text-muted">{t('release.history.versionId', { id: record.versionId })}</p><p className="mt-1 text-caption text-muted">{record.reason}</p><p className="mt-1 text-caption text-muted">{t('release.history.metadata', { actor: record.releasedBy, date })}</p></div></li>; })}</ol></section>;
}

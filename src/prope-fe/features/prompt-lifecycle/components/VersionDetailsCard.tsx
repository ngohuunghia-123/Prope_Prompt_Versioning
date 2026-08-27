import { ArrowRight, GitDiff } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { RevisionBindingDisplay } from '@/features/prompt-lifecycle/components/RevisionBindingDisplay';
import type { Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

interface VersionDetailsCardProps { revision: Revision; onCompare: () => void; onPlayground: () => void; onPromote: () => void; }
const statusTone = { inUse: 'active', approved: 'active', retired: 'disabled', inReview: 'pending', draft: 'disabled' } as const;

export function VersionDetailsCard({ revision, onCompare, onPlayground, onPromote }: VersionDetailsCardProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const { userName } = useWorkspaceDisplayNames();
  const passRate = revision.evalPassed / revision.evalTotal;
  return (
    <Card title={t('lifecycle.overview.versioning.versionDetails', { version: revision.number })}>
      <div className="grid gap-6 sm:grid-cols-2"><section><h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.versioning.metadata')}</h4><dl className="mt-2 grid gap-2 text-body"><div className="flex justify-between"><dt className="text-muted">{t('lifecycle.overview.versioning.status')}</dt><dd><StatusBadge tone={statusTone[revision.status]}>{t(`status.${revision.status}`)}</StatusBadge></dd></div><div className="flex justify-between"><dt className="text-muted">{t('lifecycle.overview.versioning.author')}</dt><dd className="text-ink">{userName(revision.author)}</dd></div><div className="flex justify-between"><dt className="text-muted">{t('lifecycle.overview.versioning.created')}</dt><dd className="text-ink">{format.date(revision.createdAt)}</dd></div></dl></section><section><h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.versioning.evalResults')}</h4><div className="mt-2 flex items-center gap-3"><div className="flex-1"><div className="flex justify-between text-caption text-muted"><span>{t('lifecycle.overview.versioning.passRate')}</span><span className="font-medium text-ink">{format.percent(passRate)}</span></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-subtle"><div className="h-full rounded-full bg-success" style={{ width: `${passRate * 100}%` }} /></div></div><span className="text-body font-medium text-ink">{revision.evalPassed}/{revision.evalTotal}</span></div><h4 className="mt-4 text-caption font-medium text-muted">{t('lifecycle.overview.versioning.costPerCall')}</h4><p className="mt-1 text-body text-ink">{format.currency(revision.cost)}</p></section></div>
      {/* What a promotion actually puts into production. A reviewer approving a
          routed revision is approving an ordered list of providers, and the
          note under it says the list is a frozen copy rather than a pointer at
          a template that can change after the approval. */}
      <section className="border-t border-border pt-4"><h4 className="text-caption font-medium text-muted">{t('lifecycle.promptDetail.binding')}</h4><div className="mt-1"><RevisionBindingDisplay revision={revision} snapshotNote /></div></section>
      <section className="border-t border-border pt-4"><h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.versioning.changeSummary')}</h4><p className="mt-1 text-body text-ink">{revision.summary}</p></section>
      <div className="flex flex-wrap gap-2"><Button intent="neutral" size="small" leadingIcon={<GitDiff aria-hidden className="size-4" />} onClick={onCompare}>{t('lifecycle.overview.versioning.compare')}</Button><Button intent="neutral" size="small" onClick={onPlayground}>{t('lifecycle.overview.versioning.playground')}</Button>{revision.status !== 'inUse' ? <Button size="small" leadingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={onPromote}>{t('lifecycle.overview.versioning.promote')}</Button> : null}</div>
    </Card>
  );
}

import { ClockCounterClockwise, Info } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Select } from '@/components/ui/Select';
import { PromptRevisionHistory } from '@/features/prompt-lifecycle/components/PromptRevisionHistory';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

const statusTone = { inUse: 'active', approved: 'active', retired: 'disabled', inReview: 'pending', draft: 'disabled' } as const;

interface PromptLifecycleHeaderProps {
  prompt: PromptDetail;
  revision: Revision;
  onSelect: (revisionId: string) => void;
  onCompare: () => void;
}

export function PromptLifecycleHeader({ prompt, revision, onSelect, onCompare }: PromptLifecycleHeaderProps) {
  const { t } = useTranslation();
  const { folderName, userName } = useWorkspaceDisplayNames();
  const [drawer, setDrawer] = useState<'history' | 'details'>();
  const folderId = prompt.folderId ?? prompt.modelName.split('/')[0];
  return (
    <header className="border-b border-border bg-surface px-4 py-4 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 tabIndex={-1} className="truncate font-display text-heading-2 text-ink">{prompt.title}</h1>
          <p className="mt-1 truncate text-caption text-muted">{folderName(folderId)}</p>
        </div>
        <div className="flex flex-1 flex-wrap items-end justify-end gap-2">
          <Select label={t('lifecycle.surface.version')} value={revision.id} options={prompt.revisions.map((item) => ({ value: item.id, label: item.number }))} onValueChange={onSelect} className="min-w-28" />
          <StatusBadge tone={statusTone[revision.status]}>{t(`status.${revision.status}`)}</StatusBadge>
          <Button type="button" intent="neutral" size="small" leadingIcon={<ClockCounterClockwise aria-hidden className="size-4" />} onClick={() => setDrawer('history')}>{t('lifecycle.surface.history')}</Button>
          <Button type="button" intent="ghost" size="small" leadingIcon={<Info aria-hidden className="size-4" />} onClick={() => setDrawer('details')}>{t('lifecycle.surface.details')}</Button>
        </div>
      </div>
      <Drawer open={drawer === 'history'} onClose={() => setDrawer(undefined)} side="right" title={t('lifecycle.surface.history')}>
        <PromptRevisionHistory prompt={prompt} selectedId={revision.id} onSelect={(id) => { onSelect(id); setDrawer(undefined); }} onCompare={onCompare} />
      </Drawer>
      <Drawer open={drawer === 'details'} onClose={() => setDrawer(undefined)} side="right" title={t('lifecycle.surface.details')}>
        <dl className="grid gap-4 overflow-y-auto p-5 text-body">
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.slug')}</dt><dd className="mt-1 break-all font-mono text-ink">{prompt.modelName}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.author')}</dt><dd className="mt-1 text-ink">{userName(revision.author)}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.provider')}</dt><dd className="mt-1 text-ink">{revision.providerConfigId || t('lifecycle.promptDetail.noBinding')}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.model')}</dt><dd className="mt-1 text-ink">{revision.upstreamModel || t('lifecycle.promptDetail.noBinding')}</dd></div>
          <div><dt className="text-caption text-muted">{t('lifecycle.promptDetail.fallback')}</dt><dd className="mt-1 whitespace-pre-wrap text-ink">{prompt.fallbackAnswer || t('lifecycle.surface.notAvailable')}</dd></div>
        </dl>
      </Drawer>
    </header>
  );
}

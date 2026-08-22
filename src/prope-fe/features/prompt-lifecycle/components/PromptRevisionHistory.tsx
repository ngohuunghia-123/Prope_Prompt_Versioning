import { GitDiff } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

const tones = { inUse: 'active', approved: 'active', retired: 'disabled', inReview: 'pending', draft: 'disabled' } as const;

export function PromptRevisionHistory({ prompt, selectedId, onSelect, onCompare }: { prompt: PromptDetail; selectedId: string; onSelect: (id: string) => void; onCompare: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="h-full overflow-y-auto p-4">
      {prompt.revisions.length > 1 ? <Button type="button" intent="neutral" size="small" leadingIcon={<GitDiff aria-hidden className="size-4" />} onClick={onCompare}>{t('lifecycle.promptCompare.action')}</Button> : null}
      <ol className="mt-4 grid gap-2">
        {prompt.revisions.map((revision) => <li key={revision.id}><button type="button" aria-pressed={revision.id === selectedId} onClick={() => onSelect(revision.id)} className={cn('w-full rounded-control border border-border p-3 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus', revision.id === selectedId && 'bg-subtle')}><span className="flex items-center justify-between gap-2"><strong className="text-body text-ink">{revision.number}</strong><StatusBadge tone={tones[revision.status]}>{t(`status.${revision.status}`)}</StatusBadge></span><span className="mt-2 block text-caption text-muted">{revision.summary}</span></button></li>)}
      </ol>
    </div>
  );
}

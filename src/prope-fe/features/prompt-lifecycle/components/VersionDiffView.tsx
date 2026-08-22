import { Sparkle, Warning } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';
import { WordHeatmap } from '@/features/prompt-lifecycle/components/WordHeatmap';
import { promptDiffOptions } from '@/features/prompt-lifecycle/queries';
import { sharedWordsOf } from '@/features/prompt-lifecycle/wordOverlap';
import type { Revision } from '@/features/prompt-lifecycle/types';

interface VersionDiffViewProps { promptId: string; baseline: Revision; candidate: Revision; onClose: () => void; onPlayground: () => void; }

export function VersionDiffView({ promptId, baseline, candidate, onClose, onPlayground }: VersionDiffViewProps) {
  const { t } = useTranslation();
  const [showSummary, setShowSummary] = useState(false);
  const diffQuery = useQuery(promptDiffOptions(promptId, baseline.id, candidate.id));
  // Same word-overlap heatmap the new-prompt comparison shows: words both
  // versions share are marked, so what carried over and what changed is legible.
  const sharedWords = useMemo(
    () => (diffQuery.data ? sharedWordsOf(diffQuery.data.before, diffQuery.data.after) : new Set<string>()),
    [diffQuery.data],
  );
  return (
    <Card title={t('lifecycle.overview.versioning.diffTitle', { a: baseline.number, b: candidate.number })} action={<Button intent="neutral" size="small" leadingIcon={<Sparkle aria-hidden className="size-4" />} onClick={() => setShowSummary((value) => !value)}>{t('lifecycle.overview.versioning.aiSummary')}</Button>}>
      <p className="flex items-center gap-2 rounded-modal bg-subtle p-3 text-caption text-muted"><Warning aria-hidden className="size-4 shrink-0 text-secondary" />{t('lifecycle.overview.versioning.diffHint')}</p>
      {showSummary ? <p className="rounded-modal border border-primary/30 bg-primary/5 p-4 text-body text-ink">{t('lifecycle.overview.versioning.aiSummaryText', { baseline: baseline.number, candidate: candidate.number })}</p> : null}
      {diffQuery.isPending ? <p role="status">{t('lifecycle.overview.versioning.loadingDiff')}</p> : diffQuery.isError ? <p role="alert" className="text-danger-text">{t('lifecycle.overview.versioning.diffError')}</p> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-modal border border-danger/30 bg-danger/5 p-4">
            <p className="text-caption text-muted">{t('lifecycle.overview.versioning.baseline')} · {baseline.number}</p>
            <WordHeatmap text={diffQuery.data.before} sharedWords={sharedWords} className="mt-3 max-h-96 overflow-auto font-mono text-caption" />
          </section>
          <section className="rounded-modal border border-success/30 bg-success/5 p-4">
            <p className="text-caption text-muted">{t('lifecycle.overview.versioning.candidate')} · {candidate.number}</p>
            <WordHeatmap text={diffQuery.data.after} sharedWords={sharedWords} className="mt-3 max-h-96 overflow-auto font-mono text-caption" />
          </section>
        </div>
      )}
      <div className="flex gap-3"><Button intent="neutral" onClick={onClose}>{t('lifecycle.overview.versioning.backToDetails')}</Button><Button onClick={onPlayground}>{t('lifecycle.overview.versioning.compareInPlayground')}</Button></div>
    </Card>
  );
}

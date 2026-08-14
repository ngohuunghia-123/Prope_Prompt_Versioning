import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { VersionDetailsCard } from '@/features/prompt-lifecycle/components/VersionDetailsCard';
import { VersionDiffView } from '@/features/prompt-lifecycle/components/VersionDiffView';
import { VersionList } from '@/features/prompt-lifecycle/components/VersionList';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';

export interface VersioningTabProps { prompt: PromptDetail; }

export function VersioningTab({ prompt }: VersioningTabProps) {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState(prompt.revisions[0]?.id ?? '');
  const [compareId, setCompareId] = useState<string>();
  const selected = prompt.revisions.find((revision) => revision.id === selectedId) ?? prompt.revisions[0];
  const candidate = prompt.revisions.find((revision) => revision.id === compareId);

  if (!selected) return <Card><p className="text-muted">—</p></Card>;

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <VersionList prompt={prompt} selectedId={selected.id} onSelect={(id) => { setSelectedId(id); setCompareId(undefined); }} onCreate={() => navigate(`/app/prompts/${prompt.id}/edit`)} />
      <div className="space-y-4">
        {candidate ? <VersionDiffView promptId={prompt.id} baseline={selected} candidate={candidate} onClose={() => setCompareId(undefined)} onPlayground={() => navigate(`/app/prompts/${prompt.id}/playground`)} /> : <VersionDetailsCard revision={selected} onCompare={() => setCompareId(prompt.revisions.find((revision) => revision.id !== selected.id)?.id ?? selected.id)} onPlayground={() => navigate(`/app/prompts/${prompt.id}/playground`)} onPromote={() => navigate(`/app/releases/${selected.id}`)} />}
      </div>
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { EvaluationTab } from '@/features/prompt-lifecycle/components/EvaluationTab';
import { MonitoringImprovementTab } from '@/features/prompt-lifecycle/components/MonitoringImprovementTab';
import { PromptComparisonWorkspace } from '@/features/prompt-lifecycle/components/PromptComparisonWorkspace';
import { PromptLifecycleHeader } from '@/features/prompt-lifecycle/components/PromptLifecycleHeader';
import { PromptSurface } from '@/features/prompt-lifecycle/components/PromptSurface';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { ReleaseTab } from '@/features/prompt-lifecycle/components/ReleaseTab';
import { lifecycleSummaryOptions } from '@/features/prompt-lifecycle/queries';
import type { OverviewTab, PromptDetail } from '@/features/prompt-lifecycle/types';

export interface PromptDetailViewProps { prompt: PromptDetail; tab?: OverviewTab; }

export function PromptDetailView({ prompt, tab: controlledTab }: PromptDetailViewProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [comparing, setComparing] = useState(false);
  const surfaceRef = useRef<HTMLDivElement>(null);
  const requestedVersion = searchParams.get('version');
  const selected = prompt.revisions.find((revision) => revision.id === requestedVersion) ?? prompt.revisions[0];
  const activeTab = controlledTab ?? 'overview';
  const revisionLabels = Object.fromEntries(prompt.revisions.map((revision) => [revision.id, revision.number]));

  const summary = useQuery({
    ...lifecycleSummaryOptions(prompt.id, selected?.id ?? ''),
    enabled: selected !== undefined,
  });

  useEffect(() => {
    if (!selected || requestedVersion === selected.id) return;
    const next = new URLSearchParams(searchParams);
    next.set('version', selected.id);
    setSearchParams(next, { replace: true });
  }, [requestedVersion, searchParams, selected, setSearchParams]);

  useEffect(() => {
    if (!selected || activeTab === 'improvement') return;
    requestAnimationFrame(() => surfaceRef.current?.querySelector<HTMLElement>('#evaluation-heading, #release-workspace-heading, #monitoring-heading, h1')?.focus());
  }, [activeTab, selected]);

  if (!selected) return <QueryState state="empty" />;

  const selectVersion = (versionId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('version', versionId);
    setSearchParams(next, { replace: true });
  };
  const improvementAnchor = searchParams.get('focus') ?? undefined;
  const overviewReturnTo = `/app/prompts/${encodeURIComponent(prompt.id)}?tab=improvement&version=${encodeURIComponent(selected.id)}${improvementAnchor ? `&focus=${encodeURIComponent(improvementAnchor)}` : ''}`;

  return (
    <div ref={surfaceRef} className="min-h-full min-w-0 bg-canvas navigation:h-full navigation:min-h-0 navigation:overflow-y-auto">
      <PromptLifecycleHeader prompt={prompt} revision={selected} onSelect={selectVersion} onCompare={() => setComparing(true)} />
      {activeTab === 'overview' && comparing ? (
        <PromptComparisonWorkspace prompt={prompt} selected={selected} onBack={() => setComparing(false)} onUseCandidate={(revisionId) => { selectVersion(revisionId); setComparing(false); }} />
      ) : null}
      {activeTab === 'overview' && !comparing ? (
        summary.isPending ? <QueryState state="loading" />
          : summary.isError || !summary.data ? <QueryState state="error" onRetry={() => void summary.refetch()} />
            : <PromptSurface prompt={prompt} revision={selected} summary={summary.data} />
      ) : null}
      {activeTab === 'evaluation' ? <EvaluationTab promptId={prompt.id} revisionId={selected.id} revisionLabels={revisionLabels} /> : null}
      {activeTab === 'release' ? <ReleaseTab prompt={prompt} versionId={selected.id} revisionLabel={selected.number} revisionLabels={revisionLabels} /> : null}
      {activeTab === 'production' || activeTab === 'improvement' ? (
        summary.isPending ? <QueryState state="loading" /> : summary.isError || !summary.data ? <QueryState state="error" onRetry={() => void summary.refetch()} /> : <MonitoringImprovementTab
          promptId={prompt.id}
          revisionId={selected.id}
          revisionLabel={selected.number}
          isReleased={summary.data.live_version_id !== null}
          focusImprovement={activeTab === 'improvement'}
          onOpenEditor={(candidateBody, findingId) => void navigate(
            `/app/prompts/${encodeURIComponent(prompt.id)}/edit?version=${encodeURIComponent(selected.id)}&from=improvement&returnTo=${encodeURIComponent(overviewReturnTo)}&focus=${encodeURIComponent(findingId)}`,
            { state: { candidateBody } },
          )}
        />
      ) : null}
    </div>
  );
}

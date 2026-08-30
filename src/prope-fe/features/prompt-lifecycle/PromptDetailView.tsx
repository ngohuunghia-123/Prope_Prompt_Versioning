import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { EvaluationTab } from '@/features/prompt-lifecycle/components/EvaluationTab';
import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';
import { MonitoringImprovementTab } from '@/features/prompt-lifecycle/components/MonitoringImprovementTab';
import { PromptComparisonWorkspace } from '@/features/prompt-lifecycle/components/PromptComparisonWorkspace';
import { PromptVersionOverview } from '@/features/prompt-lifecycle/components/PromptVersionOverview';
import { PromptVersionRail } from '@/features/prompt-lifecycle/components/PromptVersionRail';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { lifecycleSummaryOptions, useUpdateRevisionTagsMutation } from '@/features/prompt-lifecycle/queries';
import { promptOverviewUrl } from '@/features/prompt-lifecycle/promptUrls';
import type { OverviewTab, PromptDetail } from '@/features/prompt-lifecycle/types';

export interface PromptDetailViewProps { prompt: PromptDetail; tab?: OverviewTab; }

export function PromptDetailView({ prompt, tab: controlledTab }: PromptDetailViewProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const surfaceRef = useRef<HTMLDivElement>(null);
  const requestedVersion = searchParams.get('version');
  const selected = prompt.revisions.find((revision) => revision.id === requestedVersion) ?? prompt.revisions[0];
  const activeTab: OverviewTab = controlledTab ?? 'content';
  const [comparing, setComparing] = useState(false);
  const updateRevisionTags = useUpdateRevisionTagsMutation(prompt.id);
  const revisionLabels = Object.fromEntries(prompt.revisions.map((revision) => [revision.id, revision.number]));

  const summary = useQuery({
    ...lifecycleSummaryOptions(prompt.id, selected?.id ?? ''),
    enabled: selected !== undefined && (activeTab === 'monitoring' || activeTab === 'improvement'),
  });

  useEffect(() => {
    if (!selected || requestedVersion === selected.id) return;
    const next = new URLSearchParams(searchParams);
    next.set('version', selected.id);
    setSearchParams(next, { replace: true });
  }, [requestedVersion, searchParams, selected, setSearchParams]);

  useEffect(() => {
    if (!selected || activeTab === 'improvement') return;
    requestAnimationFrame(() => surfaceRef.current?.querySelector<HTMLElement>('#evaluation-heading, #monitoring-heading, #prompt-content-title, h1')?.focus());
  }, [activeTab, selected]);

  if (!selected) return <QueryState state="empty" />;

  const selectVersion = (versionId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('version', versionId);
    setSearchParams(next, { replace: true });
  };
  const improvementAnchor = searchParams.get('focus') ?? undefined;
  const overviewSearch = new URLSearchParams({ tab: 'monitoring', version: selected.id });
  if (improvementAnchor) overviewSearch.set('focus', improvementAnchor);
  const overviewReturnTo = promptOverviewUrl(prompt.modelName, overviewSearch);
  const contentReturnTo = promptOverviewUrl(prompt.modelName, new URLSearchParams({ version: selected.id }));
  const selectedIndex = prompt.revisions.findIndex((revision) => revision.id === selected.id);
  const previousBody = prompt.revisions[selectedIndex + 1]?.promptBody;

  const openEditor = (candidateBody?: string) => void navigate(
    `/app/prompts/${encodeURIComponent(prompt.id)}/edit?version=${encodeURIComponent(selected.id)}&from=content&returnTo=${encodeURIComponent(contentReturnTo)}`,
    candidateBody ? { state: { candidateBody } } : undefined,
  );

  return (
    <div ref={surfaceRef} className="min-h-full min-w-0 bg-canvas navigation:grid navigation:h-full navigation:min-h-0 navigation:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] navigation:overflow-hidden">
      <div className="min-w-0 max-w-full navigation:h-full navigation:min-h-0">
        <PromptVersionRail
          revisions={prompt.revisions}
          selectedId={selected.id}
          onSelect={selectVersion}
          onEditManually={() => openEditor()}
          onTagsChange={(revisionId, tags) => updateRevisionTags.mutate({ revisionId, tags })}
          savingRevisionId={updateRevisionTags.isPending ? updateRevisionTags.variables?.revisionId : undefined}
        />
      </div>
      <div className="min-w-0 max-w-full bg-canvas navigation:h-full navigation:min-h-0 navigation:overflow-y-auto">
        {activeTab === 'content' && comparing ? (
          <PromptComparisonWorkspace prompt={prompt} selected={selected} onBack={() => setComparing(false)} onUseCandidate={(revisionId) => { selectVersion(revisionId); setComparing(false); }} />
        ) : null}
        {activeTab === 'content' && !comparing ? (
          <PromptVersionOverview prompt={prompt} revision={selected} promptBody={selected.promptBody} previousBody={previousBody} onCompare={() => setComparing(true)} />
        ) : null}
        {activeTab === 'evaluation' ? <EvaluationTab promptId={prompt.id} revisionId={selected.id} revisionLabels={revisionLabels} /> : null}
        {activeTab === 'logs' ? (
          <section id="logs-heading" tabIndex={-1} className="focus-visible:outline-none">
            <LogsTab promptId={prompt.id} revisionId={selected.id} revisionLabel={selected.number} />
          </section>
        ) : null}
        {activeTab === 'monitoring' || activeTab === 'improvement' ? (
          summary.isPending ? <QueryState state="loading" /> : summary.isError || !summary.data ? <QueryState state="error" onRetry={() => void summary.refetch()} /> : (
            <MonitoringImprovementTab
              promptId={prompt.id}
              revisionId={selected.id}
              currentBody={selected.promptBody}
              revisionLabel={selected.number}
              revisionLabels={revisionLabels}
              releasedVersionId={summary.data.live_version_id}
              focusImprovement={activeTab === 'improvement'}
              focusFindingId={improvementAnchor}
              onOpenEditor={(candidateBody, findingId) => void navigate(
                `/app/prompts/${encodeURIComponent(prompt.id)}/edit?version=${encodeURIComponent(selected.id)}&from=improvement&returnTo=${encodeURIComponent(overviewReturnTo)}&focus=${encodeURIComponent(findingId)}`,
                { state: { candidateBody } },
              )}
            />
          )
        ) : null}
      </div>
    </div>
  );
}

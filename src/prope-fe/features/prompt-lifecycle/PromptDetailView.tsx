import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { EvaluationTab } from '@/features/prompt-lifecycle/components/EvaluationTab';
import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';
import { MonitoringImprovementTab } from '@/features/prompt-lifecycle/components/MonitoringImprovementTab';
import { PromptComparisonWorkspace } from '@/features/prompt-lifecycle/components/PromptComparisonWorkspace';
import { PromptVersionOverview } from '@/features/prompt-lifecycle/components/PromptVersionOverview';
import { PromptVersionRail } from '@/features/prompt-lifecycle/components/PromptVersionRail';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { draftToDisplayRevision, latestVersionIsPublished } from '@/features/prompt-lifecycle/draftApi';
import { lifecycleSummaryOptions, useCreateDraftMutation, usePromoteDraftMutation, useRenameDraftMutation, useUpdateRevisionTagsMutation } from '@/features/prompt-lifecycle/queries';
import { promptOverviewUrl } from '@/features/prompt-lifecycle/promptUrls';
import type { OverviewTab, PromptDetail } from '@/features/prompt-lifecycle/types';

export interface PromptDetailViewProps { prompt: PromptDetail; tab?: OverviewTab; }

export function PromptDetailView({ prompt, tab: controlledTab }: PromptDetailViewProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const surfaceRef = useRef<HTMLDivElement>(null);
  const requestedVersion = searchParams.get('version');
  const requestedDraftId = searchParams.get('draft');
  const selected = prompt.revisions.find((revision) => revision.id === requestedVersion) ?? prompt.revisions[0];
  // A draft is only selectable under its own version: a stale `?draft=` (one
  // whose promote consumed it, or from another version) falls back to the
  // version view instead of rendering a phantom.
  const selectedDraft = requestedDraftId && selected
    ? prompt.drafts.find((draft) => draft.id === requestedDraftId && draft.parentRevisionId === selected.id)
    : undefined;
  const activeTab: OverviewTab = controlledTab ?? 'content';
  const [comparing, setComparing] = useState(false);
  const updateRevisionTags = useUpdateRevisionTagsMutation(prompt.id);
  const renameDraft = useRenameDraftMutation(prompt.id);
  const createDraft = useCreateDraftMutation(prompt.id);
  const promoteDraft = usePromoteDraftMutation(prompt.id);
  // The gate behind every promote control on this screen (requirement 1).
  const canPromote = latestVersionIsPublished(prompt.revisions);
  // A prompt that is not serving any version has no published line to protect:
  // edits go straight onto the version (saved as the next revision) instead of
  // through the draft layer. The moment something is in use, drafts return.
  const directEdit = !prompt.revisions.some((revision) => revision.status === 'inUse');
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
    next.delete('draft');
    setSearchParams(next, { replace: true });
  };
  const selectDraft = (draftId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('version', selected.id);
    next.set('draft', draftId);
    setSearchParams(next, { replace: true });
    setComparing(false);
  };
  // An improvement run's draft may live under a version other than the one
  // currently selected — the run remembers its own target.
  const openImprovementDraft = (versionId: string, draftId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('version', versionId);
    next.set('draft', draftId);
    setSearchParams(next, { replace: true });
    setComparing(false);
  };
  const improvementAnchor = searchParams.get('focus') ?? undefined;
  const overviewSearch = new URLSearchParams({ tab: 'monitoring', version: selected.id });
  if (improvementAnchor) overviewSearch.set('focus', improvementAnchor);
  const overviewReturnTo = promptOverviewUrl(prompt.modelName, overviewSearch);
  const contentReturnTo = promptOverviewUrl(prompt.modelName, new URLSearchParams({ version: selected.id }));
  const selectedIndex = prompt.revisions.findIndex((revision) => revision.id === selected.id);
  const previousBody = prompt.revisions[selectedIndex + 1]?.promptBody;

  const openDraftEditor = (draftId: string) => void navigate(
    `/app/prompts/${encodeURIComponent(prompt.id)}/edit?version=${encodeURIComponent(selected.id)}&draft=${encodeURIComponent(draftId)}&from=content&returnTo=${encodeURIComponent(contentReturnTo)}`,
  );
  const openEditorDirect = (versionId: string) => void navigate(
    `/app/prompts/${encodeURIComponent(prompt.id)}/edit?version=${encodeURIComponent(versionId)}`,
  );
  const createAndOpenDraft = async () => {
    const draft = await createDraft.mutateAsync({ source: selected });
    openDraftEditor(draft.id);
  };

  return (
    <div ref={surfaceRef} className="min-h-full min-w-0 bg-canvas navigation:grid navigation:h-full navigation:min-h-0 navigation:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] navigation:overflow-hidden">
      <div className="min-w-0 max-w-full navigation:h-full navigation:min-h-0">
        <PromptVersionRail
          revisions={prompt.revisions}
          drafts={prompt.drafts}
          promptId={prompt.id}
          selectedId={selected.id}
          selectedDraftId={selectedDraft?.id}
          onSelect={selectVersion}
          onSelectDraft={selectDraft}
          onRenameDraft={(draftId, name) => renameDraft.mutate({ draftId, name })}
          onPromoteDraft={(draftId) => promoteDraft.mutate(
            { draftId, revisions: prompt.revisions },
            { onSuccess: (result) => void navigate(promptOverviewUrl(prompt.modelName, new URLSearchParams({ version: result.revisionId }))) },
          )}
          canPromote={canPromote}
          promoteBlockedReason={t('lifecycle.promptDetail.promoteBlocked')}
          directEdit={directEdit}
          onEditDirect={() => openEditorDirect(selected.id)}
          promotingDraftId={promoteDraft.isPending ? promoteDraft.variables?.draftId : undefined}
          creatingDraft={createDraft.isPending}
          onPickDraft={openDraftEditor}
          onCreateDraft={() => void createAndOpenDraft()}
          onTagsChange={(revisionId, tags) => updateRevisionTags.mutate({ revisionId, tags })}
          savingRevisionId={updateRevisionTags.isPending ? updateRevisionTags.variables?.revisionId : undefined}
          liveVersionId={prompt.revisions.find((revision) => revision.status === 'inUse')?.id}
          onReviewImprovement={(findingId) => void navigate(promptOverviewUrl(prompt.modelName, new URLSearchParams({ tab: 'monitoring', version: selected.id, focus: findingId })))}
          onOpenImprovementDraft={openImprovementDraft}
        />
      </div>
      <div className="min-w-0 max-w-full bg-canvas navigation:h-full navigation:min-h-0 navigation:overflow-y-auto">
        {activeTab === 'content' && comparing && !selectedDraft ? (
          <PromptComparisonWorkspace prompt={prompt} selected={selected} onBack={() => setComparing(false)} onUseCandidate={(revisionId) => { selectVersion(revisionId); setComparing(false); }} />
        ) : null}
        {activeTab === 'content' && !comparing && !selectedDraft ? (
          <PromptVersionOverview prompt={prompt} revision={selected} promptBody={selected.promptBody} previousBody={previousBody} onCompare={() => setComparing(true)} />
        ) : null}
        {activeTab === 'content' && !comparing && selectedDraft ? (
          <PromptVersionOverview
            prompt={prompt}
            revision={draftToDisplayRevision(selectedDraft, selected)}
            promptBody={selectedDraft.promptBody}
            previousBody={selected.promptBody}
            draftName={selectedDraft.name}
          />
        ) : null}
        {activeTab === 'evaluation' ? <EvaluationTab prompt={prompt} revision={selected} revisionLabels={revisionLabels} /> : null}
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

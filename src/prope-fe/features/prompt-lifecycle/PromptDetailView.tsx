import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { ProductionTab } from '@/features/prompt-lifecycle/components/ProductionTab';
import { EvaluationTab } from '@/features/prompt-lifecycle/components/EvaluationTab';
import { PromptAiEditDrawer } from '@/features/prompt-lifecycle/components/PromptAiEditDrawer';
import { PromptComparisonWorkspace } from '@/features/prompt-lifecycle/components/PromptComparisonWorkspace';
import { ReleaseTab } from '@/features/prompt-lifecycle/components/ReleaseTab';
import { PromptVersionOverview } from '@/features/prompt-lifecycle/components/PromptVersionOverview';
import { PromptVersionRail } from '@/features/prompt-lifecycle/components/PromptVersionRail';
import { useAiPromptEditMutation, useUpdateRevisionTagsMutation } from '@/features/prompt-lifecycle/queries';
import type { PromptDetail, OverviewTab } from '@/features/prompt-lifecycle/types';

export interface PromptDetailViewProps {
  prompt: PromptDetail;
  tab?: OverviewTab;
}

export function PromptDetailView({ prompt, tab: controlledTab }: PromptDetailViewProps) {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState(prompt.revisions[0]?.id ?? '');
  const [appliedBodies, setAppliedBodies] = useState<Record<string, string>>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [aiDraft, setAiDraft] = useState('');
  const [comparing, setComparing] = useState(false);
  const aiEdit = useAiPromptEditMutation();
  const updateRevisionTags = useUpdateRevisionTagsMutation(prompt.id);
  // A confirmed write lands here and points at the rail, because the revision it
  // just created is the thing the person agreed to and has not yet seen.
  const { highlight } = useAgentSurface();
  const selected = prompt.revisions.find((revision) => revision.id === selectedId) ?? prompt.revisions[0];
  const activeTab = controlledTab ?? 'overview';

  if (!selected) return null;
  const selectedBody = appliedBodies[selected.id] ?? selected.promptBody;
  const selectedIndex = prompt.revisions.findIndex((revision) => revision.id === selected.id);
  const previousBody = prompt.revisions[selectedIndex + 1]?.promptBody;
  // The Eval tab's trend labels its columns with the rail's own numbering, so a
  // bar and a revision in the list are recognisably the same thing.
  const revisionLabels = Object.fromEntries(prompt.revisions.map((revision) => [revision.id, revision.number]));
  const openAiDrawer = () => {
    setAiDraft(selectedBody);
    setDrawerOpen(true);
    aiEdit.mutate(
      { promptId: prompt.id, revisionId: selected.id, promptBody: selectedBody },
      { onSuccess: (result) => setAiDraft(result.promptBody) },
    );
  };
  const applyAiDraft = () => {
    setAppliedBodies((current) => ({ ...current, [selected.id]: aiDraft }));
    setDrawerOpen(false);
  };

  return (
    <div className={cn('min-h-full min-w-0 bg-canvas navigation:h-full navigation:min-h-0', !comparing && 'navigation:grid navigation:grid-cols-[minmax(18rem,30%)_minmax(0,1fr)]')}>
      {/* `flex` so the rail keeps stretching to the row: it was a grid item and
          is now a flex child, and `min-h-full` on it depends on that. */}
      <div className={cn('min-w-0 max-w-full transition-shadow navigation:h-full navigation:min-h-0', comparing ? 'hidden' : 'flex', highlight === 'version-rail' && 'ring-2 ring-inset ring-secondary')}>
        <PromptVersionRail
          revisions={prompt.revisions}
          selectedId={selected.id}
          onSelect={setSelectedId}
          onEditWithAi={openAiDrawer}
          onEditManually={() => void navigate(`/app/prompts/${prompt.id}/edit?version=${encodeURIComponent(selected.id)}`)}
          onTagsChange={(revisionId, tags) => updateRevisionTags.mutate({ revisionId, tags })}
          savingRevisionId={updateRevisionTags.isPending ? updateRevisionTags.variables?.revisionId : undefined}
        />
      </div>
      <div className="min-w-0 max-w-full bg-canvas navigation:h-full navigation:min-h-0 navigation:overflow-y-auto">
        {activeTab === 'overview' ? (
          comparing ? <PromptComparisonWorkspace prompt={prompt} selected={selected} onBack={() => setComparing(false)} onUseCandidate={(revisionId) => { setSelectedId(revisionId); setComparing(false); void navigate(`/app/prompts/${prompt.id}?tab=release`); }} />
            : <PromptVersionOverview prompt={prompt} revision={selected} promptBody={selectedBody} previousBody={previousBody} onCompare={() => setComparing(true)} />
        ) : null}
        {activeTab === 'release' ? (
          <div>
            <ReleaseTab
              prompt={prompt}
              versionId={selected.id}
              revisionLabel={selected.number}
              revisionLabels={revisionLabels}
            />
          </div>
        ) : null}
        {activeTab === 'production' ? <div><ProductionTab promptId={prompt.id} revisionId={selected.id} revisionLabel={selected.number} /></div> : null}
        {activeTab === 'evaluation' ? (
          <div>
            <EvaluationTab promptId={prompt.id} revisionId={selected.id} revisionLabels={revisionLabels} />
          </div>
        ) : null}
      </div>
      <PromptAiEditDrawer open={drawerOpen} value={aiDraft} loading={aiEdit.isPending} error={aiEdit.isError} onChange={setAiDraft} onClose={() => setDrawerOpen(false)} onApply={applyAiDraft} />
    </div>
  );
}

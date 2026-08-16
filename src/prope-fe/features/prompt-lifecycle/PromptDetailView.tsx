import { useState } from 'react';
import { cn } from '@/lib/cn';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';
import { ProductionTab } from '@/features/prompt-lifecycle/components/ProductionTab';
import { EvaluationTab } from '@/features/prompt-lifecycle/components/EvaluationTab';
import { PromptAiEditDrawer } from '@/features/prompt-lifecycle/components/PromptAiEditDrawer';
import { PromptDetailTabs } from '@/features/prompt-lifecycle/components/PromptDetailTabs';
import { PromptIndexPanel } from '@/features/prompt-lifecycle/components/PromptIndexPanel';
import { ReleaseTab } from '@/features/prompt-lifecycle/components/ReleaseTab';
import { PromptVersionOverview } from '@/features/prompt-lifecycle/components/PromptVersionOverview';
import { PromptVersionRail } from '@/features/prompt-lifecycle/components/PromptVersionRail';
import { useAiPromptEditMutation } from '@/features/prompt-lifecycle/queries';
import type { PromptDetail, OverviewTab } from '@/features/prompt-lifecycle/types';

export interface PromptDetailViewProps {
  prompt: PromptDetail;
  tab?: OverviewTab;
}

export function PromptDetailView({ prompt, tab: controlledTab }: PromptDetailViewProps) {
  const [selectedId, setSelectedId] = useState(prompt.revisions[0]?.id ?? '');
  const [appliedBodies, setAppliedBodies] = useState<Record<string, string>>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [aiDraft, setAiDraft] = useState('');
  const aiEdit = useAiPromptEditMutation();
  // A confirmed write lands here and points at the rail, because the revision it
  // just created is the thing the person agreed to and has not yet seen.
  const { highlight } = useAgentSurface();
  const selected = prompt.revisions.find((revision) => revision.id === selectedId) ?? prompt.revisions[0];
  const activeTab = controlledTab ?? 'versioning';

  if (!selected) return null;
  const selectedBody = appliedBodies[selected.id] ?? selected.promptBody;
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
    <div className="overflow-hidden rounded-modal border border-border bg-canvas shadow-panel lg:grid lg:grid-cols-4">
      {/* `flex` so the rail keeps stretching to the row: it was a grid item and
          is now a flex child, and `min-h-full` on it depends on that. */}
      <div className={cn('flex transition-shadow', highlight === 'version-rail' && 'ring-2 ring-inset ring-secondary')}>
        <PromptVersionRail
          revisions={prompt.revisions}
          selectedId={selected.id}
          onSelect={setSelectedId}
          onEditWithAi={openAiDrawer}
          showEditAction={activeTab === 'versioning'}
        />
      </div>
      <div className="min-w-0 lg:col-span-3">
        <PromptDetailTabs promptId={prompt.id} />
        {activeTab === 'versioning' ? (
          <>
            <PromptVersionOverview prompt={prompt} revision={selected} promptBody={selectedBody} />
            <div className="p-4 sm:p-6 sm:pt-0"><PromptIndexPanel prompt={prompt} /></div>
          </>
        ) : null}
        {activeTab === 'release' ? (
          <div className="p-4 sm:p-6">
            <ReleaseTab
              prompt={prompt}
              versionId={selected.id}
              revisionLabel={selected.number}
              revisionLabels={revisionLabels}
            />
          </div>
        ) : null}
        {activeTab === 'logs' ? (
          <div className="p-4 sm:p-6">
            <LogsTab promptId={prompt.id} revisionId={selected.id} revisionLabel={selected.number} />
          </div>
        ) : null}
        {activeTab === 'production' ? <div className="p-4 sm:p-6"><ProductionTab promptId={prompt.id} /></div> : null}
        {activeTab === 'evaluation' ? (
          <div className="p-4 sm:p-6">
            <EvaluationTab promptId={prompt.id} revisionId={selected.id} revisionLabels={revisionLabels} />
          </div>
        ) : null}
      </div>
      <PromptAiEditDrawer open={drawerOpen} value={aiDraft} loading={aiEdit.isPending} error={aiEdit.isError} onChange={setAiDraft} onClose={() => setDrawerOpen(false)} onApply={applyAiDraft} />
    </div>
  );
}

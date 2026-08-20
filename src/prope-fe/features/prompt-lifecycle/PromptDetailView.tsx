import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';
import { ImprovementTab } from '@/features/prompt-lifecycle/components/ImprovementTab';
import { ProductionTab } from '@/features/prompt-lifecycle/components/ProductionTab';
import { EvaluationTab } from '@/features/prompt-lifecycle/components/EvaluationTab';
import { PromptAiEditDrawer } from '@/features/prompt-lifecycle/components/PromptAiEditDrawer';
import { PromptIndexPanel } from '@/features/prompt-lifecycle/components/PromptIndexPanel';
import { ReleaseTab } from '@/features/prompt-lifecycle/components/ReleaseTab';
import { ReadinessPanel } from '@/features/prompt-lifecycle/components/ReadinessPanel';
import { PromptVersionOverview } from '@/features/prompt-lifecycle/components/PromptVersionOverview';
import { PromptVersionRail } from '@/features/prompt-lifecycle/components/PromptVersionRail';
import { useAiPromptEditMutation } from '@/features/prompt-lifecycle/queries';
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
    <div className="min-h-full min-w-0 bg-canvas lg:grid lg:grid-cols-[30%_70%]">
      {/* `flex` so the rail keeps stretching to the row: it was a grid item and
          is now a flex child, and `min-h-full` on it depends on that. */}
      <div className={cn('flex min-w-0 max-w-full transition-shadow', highlight === 'version-rail' && 'ring-2 ring-inset ring-secondary')}>
        <PromptVersionRail
          revisions={prompt.revisions}
          selectedId={selected.id}
          onSelect={setSelectedId}
          onEditWithAi={openAiDrawer}
          onEditManually={() => void navigate(`/app/prompts/${prompt.id}/edit`)}
        />
      </div>
      <div className="min-w-0 max-w-full">
        {activeTab === 'versioning' ? (
          <>
            <PromptVersionOverview prompt={prompt} revision={selected} promptBody={selectedBody} />
            {/*
              ADR-0067's card, on the revision the rail has selected. **Beside the
              body, never above it** — the same placement rule the review screen
              follows for the eval result: a readiness finding is context for the
              thing being read, and a panel that pushed the prompt below the fold
              would be a panel asserting it matters more than the prompt does.

              Nothing here blocks. A prompt with six warnings saves, submits and
              releases exactly as one with none.
            */}
            <div className="border-t border-border p-4 sm:p-6">
              <ReadinessPanel promptId={prompt.id} versionId={selected.id} trigger="edit" />
            </div>
            <div className="border-t border-border"><PromptIndexPanel prompt={prompt} /></div>
          </>
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
        {activeTab === 'logs' ? (
          <div>
            <LogsTab promptId={prompt.id} revisionId={selected.id} revisionLabel={selected.number} />
          </div>
        ) : null}
        {activeTab === 'production' ? <div><ProductionTab promptId={prompt.id} /></div> : null}
        {/*
          ADR-0068's tab. One prompt's degradation history, beside ADR-0055's
          call-records tab — the two read the same traffic and answer different
          questions: Logs says what happened, this says what changed.

          Accepting a proposal navigates to the editor with the candidate body.
          It does NOT save: the revision is written by prompt-registry on the
          person's own second, explicit act (SR-6, ADR-0066).
        */}
        {activeTab === 'improvement' ? (
          <div>
            <ImprovementTab
              promptId={prompt.id}
              onOpenEditor={(candidateBody) =>
                void navigate(`/app/prompts/${prompt.id}/edit`, { state: { candidateBody } })
              }
            />
          </div>
        ) : null}
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

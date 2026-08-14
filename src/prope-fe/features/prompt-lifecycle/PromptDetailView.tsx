import { useState } from 'react';
import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';
import { ProductionTab } from '@/features/prompt-lifecycle/components/ProductionTab';
import { EvaluationTab } from '@/features/prompt-lifecycle/components/EvaluationTab';
import { PromptAiEditDrawer } from '@/features/prompt-lifecycle/components/PromptAiEditDrawer';
import { PromptDetailTabs } from '@/features/prompt-lifecycle/components/PromptDetailTabs';
import { PromptIndexPanel } from '@/features/prompt-lifecycle/components/PromptIndexPanel';
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
  const selected = prompt.revisions.find((revision) => revision.id === selectedId) ?? prompt.revisions[0];
  const activeTab = controlledTab ?? 'versioning';

  if (!selected) return null;
  const selectedBody = appliedBodies[selected.id] ?? selected.promptBody;
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
      <PromptVersionRail
        revisions={prompt.revisions}
        selectedId={selected.id}
        onSelect={setSelectedId}
        onEditWithAi={openAiDrawer}
        showEditAction={activeTab === 'versioning'}
      />
      <div className="min-w-0 lg:col-span-3">
        <PromptDetailTabs promptId={prompt.id} />
        {activeTab === 'versioning' ? (
          <>
            <PromptVersionOverview prompt={prompt} revision={selected} promptBody={selectedBody} />
            <div className="p-4 sm:p-6 sm:pt-0"><PromptIndexPanel prompt={prompt} /></div>
          </>
        ) : null}
        {activeTab === 'logs' ? <div className="p-4 sm:p-6"><LogsTab promptId={prompt.id} revisionId={selected.id} /></div> : null}
        {activeTab === 'production' ? <div className="p-4 sm:p-6"><ProductionTab promptId={prompt.id} /></div> : null}
        {activeTab === 'evaluation' ? <div className="p-4 sm:p-6"><EvaluationTab promptId={prompt.id} revisionId={selected.id} /></div> : null}
      </div>
      <PromptAiEditDrawer open={drawerOpen} value={aiDraft} loading={aiEdit.isPending} error={aiEdit.isError} onChange={setAiDraft} onClose={() => setDrawerOpen(false)} onApply={applyAiDraft} />
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';
import { ClockCounterClockwise, Play } from '@phosphor-icons/react';
import { useMemo, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { DatasetDraftDialog } from '@/features/prompt-lifecycle/components/DatasetDraftDialog';
import {
  DatasetEditorDialog,
  type DatasetEditorMode,
} from '@/features/prompt-lifecycle/components/DatasetEditorDialog';
import { EvalDatasetSuggestions } from '@/features/prompt-lifecycle/components/EvalDatasetSuggestions';
import { EvalDatasetTree } from '@/features/prompt-lifecycle/components/EvalDatasetTree';
import { EvalRunConsole } from '@/features/prompt-lifecycle/components/EvalRunConsole';
import { EvalWorkspaceAlerts } from '@/features/prompt-lifecycle/components/EvalWorkspaceAlerts';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { evaluationIsLive } from '@/features/prompt-lifecycle/evalApi';
import {
  MAX_ATTACHED_DATASETS,
  type EvalDataset,
  type EvalRunHandle,
} from '@/features/prompt-lifecycle/evalTypes';
import {
  evalAttachmentsOptions,
  evalLibraryOptions,
  promptEvalRunsOptions,
  useCancelEvalRunMutation,
  useDeleteEvalDatasetMutation,
  useDraftEvalDatasetMutation,
  useReplaceDatasetAttachmentsMutation,
  useStartEvalRunsMutation,
} from '@/features/prompt-lifecycle/queries';
import { isTerminal } from '@/features/prompt-lifecycle/evalTypes';
import { useEvalRunReports } from '@/features/prompt-lifecycle/useEvalRunReports';
import { revisionIsBound, type PromptDetail, type Revision } from '@/features/prompt-lifecycle/types';
import { cn } from '@/lib/cn';

interface EvalWorkspacePanelProps {
  /** The prompt whose revision is under evaluation; the folder is where a new
   * or drafted set is filed by default, because a dataset written while
   * looking at one prompt is usually about that prompt's domain. */
  prompt: PromptDetail;
  revision: Revision;
  /** Opens the run history drawer the tab owns. */
  onOpenHistory: () => void;
  /** The revision's evidence — tiles, in-flight runs, issues, analysis —
   * rendered in the workspace's right column, beside the console. */
  results?: ReactNode;
}

/**
 * The eval workspace: choose what will measure this prompt, and optionally
 * measure it now. Lives on the prompt detail page's evaluation tab.
 *
 * **Two separable things happen here and only one of them is required.**
 * Ticking a dataset attaches it — one row, no provider call — and that is what
 * somebody leaving straight for the playground has still accomplished. Pressing
 * "Chạy thử" materialises those attachments into immutable suite versions and
 * starts the runs, which needs a provider binding on the revision and a worker
 * to claim them. Keeping the two apart is why this panel is useful before the
 * stack is fully configured.
 */
export function EvalWorkspacePanel({ prompt, revision, onOpenHistory, results }: EvalWorkspacePanelProps) {
  const { t } = useTranslation();
  const { highlight } = useAgentSurface();
  const navigate = useNavigate();
  const promptId = prompt.id;
  const versionId = revision.id;

  const libraryQuery = useQuery(evalLibraryOptions);
  const attachmentsQuery = useQuery(evalAttachmentsOptions(promptId));
  const runsQuery = useQuery(promptEvalRunsOptions(promptId, versionId));

  const replaceAttachments = useReplaceDatasetAttachmentsMutation(promptId);
  const startRuns = useStartEvalRunsMutation(promptId);
  const cancelRun = useCancelEvalRunMutation();
  const draftDataset = useDraftEvalDatasetMutation(promptId);
  const removeDataset = useDeleteEvalDatasetMutation(promptId);
  const [handles, setHandles] = useState<EvalRunHandle[]>([]);
  const { reports, live } = useEvalRunReports(handles);
  // The row that holds the dataset panel and the run console; the suggestion
  // popover sizes itself against it so its proposals span the workspace.
  const workspaceRowRef = useRef<HTMLDivElement>(null);

  // Two views of the same workspace. Once this revision has at least one run,
  // the tab defaults to results: the setup controls (suggest, draft, new) hide
  // and the run button becomes "Chạy bộ kiểm thử mới", which flips back to the
  // setup view so the person can pick further sets. A version without runs has
  // nothing to show but the setup, so it starts there.
  const [setupMode, setSetupMode] = useState(false);
  const showSetup = (runsQuery.data ?? []).length === 0 || setupMode;

  const [editor, setEditor] = useState<{ mode: DatasetEditorMode; datasetId?: string }>();
  const [pendingDelete, setPendingDelete] = useState<EvalDataset>();
  const [deleteNote, setDeleteNote] = useState<{ name: string; detached: number }>();
  const [draftDialogOpen, setDraftDialogOpen] = useState(false);

  const { attached, measured, stale } = useMemo(() => {
    const attachedIds = new Set<string>();
    const measuredIds = new Set<string>();
    const staleIds = new Set<string>();
    for (const attachment of attachmentsQuery.data ?? []) {
      attachedIds.add(attachment.dataset_id);
      if (attachment.suite_id) measuredIds.add(attachment.dataset_id);
      if (attachment.stale) staleIds.add(attachment.dataset_id);
    }
    return { attached: attachedIds, measured: measuredIds, stale: staleIds };
  }, [attachmentsQuery.data]);

  // A run dispatches through provider-access using the revision's own binding,
  // so without one every case comes back a dispatch error and the panel reads as
  // a broken prompt. The engine is still the authority; this only keeps the
  // button from starting twenty calls that are all going to fail the same way.
  // A route counts too: ADR-0069 lets a revision bind an ordered list instead of
  // a pair. The run itself takes rung 1 only, never a failover (A-164).
  const live_api = evaluationIsLive();
  const hasProviderBinding = revisionIsBound(revision);
  const promptFolder = prompt.modelName.split('/')[0] ?? '';
  const folders = [...new Set((libraryQuery.data ?? []).map((dataset) => dataset.folder))];

  if (libraryQuery.isPending || attachmentsQuery.isPending) {
    return <QueryState state="loading" />;
  }

  const runnable = attached.size > 0 && hasProviderBinding && live_api;
  const runDisabledReason = !live_api
    ? t('lifecycle.evalRun.disabled.offline')
    : attached.size === 0
      ? t('lifecycle.evalRun.disabled.noDataset')
      : !hasProviderBinding
        ? t('lifecycle.evalRun.disabled.noProvider')
        : undefined;

  // Only the runs that have not reached a terminal status are worth a cancel
  // press; the rest would answer 409 and teach the user nothing.
  const cancellableRunIds = reports
    .filter((report) => report.run === null || !isTerminal(report.run.status))
    .map((report) => report.handle.run_id);

  function toggle(datasetId: string, attach: boolean) {
    const next = attach
      ? [...attached, datasetId]
      : [...attached].filter((id) => id !== datasetId);
    replaceAttachments.mutate(next.slice(0, MAX_ATTACHED_DATASETS));
  }

  // Where the "add provider" handoff lands. `focus=provider-binding` opens the
  // editor's binding fields, and `returnTo` brings the person back here — the
  // tab they were on — rather than stranding them in the editor.
  const providerBindingEditor = `/app/prompts/${promptId}/edit?version=${encodeURIComponent(versionId)}&focus=provider-binding&returnTo=${encodeURIComponent(`/app/prompts/${promptId}?tab=evaluation&version=${encodeURIComponent(versionId)}`)}`;

  return (
    <div className="grid gap-3 navigation:min-h-0 navigation:max-h-full navigation:flex-1 navigation:grid-rows-[auto_minmax(0,1fr)] navigation:overflow-hidden">
      <EvalWorkspaceAlerts
        offline={!live_api}
        attachError={replaceAttachments.isError}
        runError={startRuns.isError}
        cancelError={cancelRun.isError}
        draftError={draftDataset.isError}
        needsProvider={live_api && attached.size > 0 && !hasProviderBinding}
        onAddProvider={() => void navigate(providerBindingEditor)}
        deleteNote={deleteNote}
        onDismissDeleteNote={() => setDeleteNote(undefined)}
      />
      {/* The advisor's proposals and the run history live inside the tree's
          action column: a suggestion ends in a tick, and the tick's controls
          are directly below. */}
      <div
        ref={workspaceRowRef}
        className={cn(
          'grid items-start gap-4 navigation:min-h-0 navigation:items-stretch md:grid-cols-[fit-content(calc(var(--container-drawer)+6rem))_minmax(0,1fr)]',
          highlight === 'eval-runs' && 'rounded-modal ring-2 ring-secondary ring-offset-2 ring-offset-canvas',
        )}
      >
        <div className="w-full min-w-0">
          <EvalDatasetTree
            datasets={libraryQuery.data ?? []}
            attached={attached}
            measured={measured}
            stale={stale}
            saving={replaceAttachments.isPending}
            disabled={!live_api}
            drafting={draftDataset.isPending}
            showManagement={showSetup}
            extraActions={
              <>
                {showSetup ? (
                  <EvalDatasetSuggestions
                    promptId={promptId}
                    versionId={versionId}
                    attached={attached}
                    disabled={!live_api}
                    containerRef={workspaceRowRef}
                    onAttach={(datasetId) => toggle(datasetId, true)}
                  />
                ) : null}
                <Button
                  type="button"
                  intent="ghost"
                  className="w-full"
                  leadingIcon={<ClockCounterClockwise aria-hidden className="size-4" />}
                  onClick={onOpenHistory}
                >
                  {t('lifecycle.surface.evaluation.history')}
                </Button>
              </>
            }
            onToggle={toggle}
            onCreate={() => setEditor({ mode: 'create' })}
            onDraft={() => setDraftDialogOpen(true)}
            onEdit={(datasetId) => setEditor({ mode: 'edit', datasetId })}
            onCopy={(datasetId) => setEditor({ mode: 'copy', datasetId })}
            onDelete={(dataset) => setPendingDelete(dataset)}
          />
        </div>
        {/* The evidence sits in the console's column: results view keeps tiles
            and issues beside the tree so the whole picture fits one screen
            instead of pushing them below the workspace row. The run console —
            and the suite reports inside it — belong to the new-run state
            alone; results view offers only the button that enters it. */}
        <div className="grid min-w-0 content-start gap-3 navigation:min-h-0 navigation:overflow-y-auto">
          {showSetup ? (
            <EvalRunConsole
              attachedCount={attached.size}
              runnable={runnable}
              runDisabledReason={runDisabledReason}
              busy={startRuns.isPending || live}
              hasReports={handles.length > 0}
              reports={reports}
              showReports
              onCancel={
                setupMode && (runsQuery.data ?? []).length > 0
                  ? () => setSetupMode(false)
                  : undefined
              }
              cancellable={cancellableRunIds.length > 0}
              cancelling={cancelRun.isPending}
              onCancelRun={() => cancellableRunIds.forEach((runId) => cancelRun.mutate(runId))}
              onRun={() =>
                startRuns.mutate(versionId, {
                  onSuccess: (accepted) => setHandles(accepted.runs),
                })
              }
            />
          ) : (
            <div className="flex justify-end">
              <Button
                type="button"
                intent="primary"
                leadingIcon={<Play aria-hidden weight="fill" className="size-4" />}
                onClick={() => setSetupMode(true)}
              >
                {t('lifecycle.evalRun.runNew')}
              </Button>
            </div>
          )}
          {results}
        </div>
      </div>

      <DatasetEditorDialog
        open={editor !== undefined}
        mode={editor?.mode ?? 'create'}
        datasetId={editor?.datasetId}
        promptId={promptId}
        defaultFolder={promptFolder}
        folders={folders}
        onClose={() => setEditor(undefined)}
        onSaved={() => setEditor(undefined)}
      />

      <DatasetDraftDialog
        open={draftDialogOpen}
        loading={draftDataset.isPending}
        onClose={() => setDraftDialogOpen(false)}
        onDraft={(brief) => draftDataset.mutate(
          { versionId, folder: promptFolder, brief },
          { onSuccess: () => setDraftDialogOpen(false) },
        )}
      />

      <Modal
        open={pendingDelete !== undefined}
        destructive
        title={t('lifecycle.evalDatasets.deleteTitle', { name: pendingDelete?.name ?? '' })}
        description={
          attached.has(pendingDelete?.dataset_id ?? '')
            ? t('lifecycle.evalDatasets.deleteBodyAttached')
            : t('lifecycle.evalDatasets.deleteBody')
        }
        confirmLabel={t('lifecycle.evalDatasets.deleteConfirm')}
        confirmLoading={removeDataset.isPending}
        onClose={() => setPendingDelete(undefined)}
        onConfirm={() => {
          const target = pendingDelete;
          if (!target) return;
          removeDataset.mutate(target.dataset_id, {
            onSuccess: (result) => {
              setPendingDelete(undefined);
              setDeleteNote({ name: target.name, detached: result.detached });
            },
          });
        }}
      />
    </div>
  );
}

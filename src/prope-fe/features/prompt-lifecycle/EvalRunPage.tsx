import { ArrowLeft, ArrowRight, Play } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { BottomActionDock } from '@/components/BottomActionDock';
import { Modal } from '@/components/ui/Modal';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { DatasetDraftDialog } from '@/features/prompt-lifecycle/components/DatasetDraftDialog';
import {
  DatasetEditorDialog,
  type DatasetEditorMode,
} from '@/features/prompt-lifecycle/components/DatasetEditorDialog';
import { EvalDatasetTree } from '@/features/prompt-lifecycle/components/EvalDatasetTree';
import { EvalRunResults } from '@/features/prompt-lifecycle/components/EvalRunResults';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { RegistrationSteps } from '@/features/prompt-lifecycle/components/RegistrationSteps';
import { evaluationIsLive } from '@/features/prompt-lifecycle/evalApi';
import { revisionIsBound } from '@/features/prompt-lifecycle/types';
import {
  MAX_ATTACHED_DATASETS,
  type EvalDataset,
  type EvalRunHandle,
} from '@/features/prompt-lifecycle/evalTypes';
import {
  evalAttachmentsOptions,
  evalLibraryOptions,
  promptOptions,
  useDeleteEvalDatasetMutation,
  useDraftEvalDatasetMutation,
  useReplaceDatasetAttachmentsMutation,
  useStartEvalRunsMutation,
} from '@/features/prompt-lifecycle/queries';
import { useEvalRunReports } from '@/features/prompt-lifecycle/useEvalRunReports';
import { internalReturnTo, lifecycleOrigin } from '@/features/prompt-lifecycle/lifecycleNavigation';
import { cn } from '@/lib/cn';

/**
 * Step 4 of registration: choose what will measure this prompt, and optionally
 * measure it now.
 *
 * **Two separable things happen here and only one of them is required.**
 * Ticking a dataset attaches it — one row, no provider call — and that is what
 * somebody leaving straight for the playground has still accomplished. Pressing
 * "Chạy thử" materialises those attachments into immutable suite versions and
 * starts the runs, which needs a provider binding on the revision and a worker
 * to claim them. Keeping the two apart is why this page is useful before the
 * stack is fully configured.
 *
 * The revision under evaluation comes from `?version=`, not from component
 * state, so a refresh does not lose it. When it is absent — somebody arrived
 * from a link rather than from the composer — the prompt's latest revision is
 * used, because that is the one they were just looking at.
 */
export function EvalRunPage() {
  const { t } = useTranslation();
  const { highlight } = useAgentSurface();
  const { promptId = '' } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const origin = lifecycleOrigin(searchParams.get('from'));
  const returnTo = internalReturnTo(searchParams.get('returnTo'));

  const promptQuery = useQuery(promptOptions(promptId));
  const libraryQuery = useQuery(evalLibraryOptions);
  const attachmentsQuery = useQuery(evalAttachmentsOptions(promptId));

  const replaceAttachments = useReplaceDatasetAttachmentsMutation(promptId);
  const startRuns = useStartEvalRunsMutation(promptId);
  const draftDataset = useDraftEvalDatasetMutation(promptId);
  const removeDataset = useDeleteEvalDatasetMutation(promptId);
  const [handles, setHandles] = useState<EvalRunHandle[]>([]);
  const { reports, live } = useEvalRunReports(handles);

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

  const versionId = searchParams.get('version') ?? promptQuery.data?.revisions?.[0]?.id ?? '';

  // A run dispatches through provider-access using the revision's own binding,
  // so without one every case comes back a dispatch error and the page reads as
  // a broken prompt. The engine is still the authority; this only keeps the
  // button from starting twenty calls that are all going to fail the same way.
  //
  // Read from the revision being RUN, not from `prompt.provider` — which is the
  // latest revision's binding whatever `?version=` says. And a route counts:
  // ADR-0069 lets a revision bind an ordered list instead of a pair, and the
  // pair-only check refused those outright *and* offered a "fix the binding"
  // deep link into a composer whose binding was already correct — a loop with
  // no exit. The run itself takes rung 1 only, never a failover (A-164).
  const runningRevision = promptQuery.data?.revisions.find((revision) => revision.id === versionId)
    ?? promptQuery.data?.revisions[0];
  const hasProviderBinding = revisionIsBound(runningRevision);

  const live_api = evaluationIsLive();

  function toggle(datasetId: string, attach: boolean) {
    const next = attach
      ? [...attached, datasetId]
      : [...attached].filter((id) => id !== datasetId);
    replaceAttachments.mutate(next.slice(0, MAX_ATTACHED_DATASETS));
  }

  // The prompt's own namespace is where a new or drafted set is filed by
  // default: a dataset written while looking at one prompt is usually about
  // that prompt's domain, and the folder is that domain.
  const promptFolder = promptQuery.data?.modelName.split('/')[0] ?? '';
  const folders = [...new Set((libraryQuery.data ?? []).map((dataset) => dataset.folder))];

  if (promptQuery.isPending || libraryQuery.isPending || attachmentsQuery.isPending) {
    return <QueryState state="loading" />;
  }
  if (promptQuery.isError) {
    return <QueryState state="error" onRetry={() => void promptQuery.refetch()} />;
  }

  const runnable = attached.size > 0 && hasProviderBinding && versionId !== '' && live_api;
  const runDisabledReason = !live_api
    ? t('lifecycle.evalRun.disabled.offline')
    : attached.size === 0
      ? t('lifecycle.evalRun.disabled.noDataset')
      : !hasProviderBinding
        ? t('lifecycle.evalRun.disabled.noProvider')
        : versionId === ''
          ? t('lifecycle.evalRun.disabled.noRevision')
          : undefined;

  /**
   * The way back to step 3, and the reason it is a link to the editor rather
   * than a `history.back()`: this page is where somebody discovers the prompt
   * they just registered is bound to the wrong provider, or to none. Until now
   * there was nothing on the screen that led anywhere but forward, so the only
   * move left was to abandon the prompt and register it again.
   *
   * It carries `?version=` so the editor opens on the revision under
   * evaluation. Saving there appends a NEW revision rather than changing this
   * one — a revision is immutable once written (A-021) — and the composer
   * navigates straight back here with the new `?version=`, which is what makes
   * the round trip a loop rather than a detour.
   *
   * `from=evaluation` is what lets the editor offer the way back here for
   * somebody who opened it and changed their mind. Without it the editor cannot
   * tell this arrival apart from one out of the prompt's own page, where a link
   * to an evaluation nobody asked for would be noise.
   */
  const editParams = new URLSearchParams();
  if (versionId) editParams.set('version', versionId);
  editParams.set('from', origin ?? 'evaluation');
  if (returnTo) editParams.set('returnTo', returnTo);
  const focus = searchParams.get('focus');
  if (focus) editParams.set('focus', focus);
  const backToEdit = `/app/prompts/${promptId}/edit?${editParams.toString()}`;
  const providerEditParams = new URLSearchParams(editParams);
  providerEditParams.set('focus', 'provider-binding');
  const providerBindingEditor = `/app/prompts/${promptId}/edit?${providerEditParams.toString()}`;
  const promptDestination = returnTo ?? `/app/prompts/${promptId}?version=${encodeURIComponent(versionId)}`;

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-4 pb-24">
      <RegistrationSteps current="evaluate" targets={{ compose: backToEdit }} />
      {!live_api ? (
        <Notification tone="info" title={t('lifecycle.evalRun.unavailable')}>
          {t('lifecycle.evalRun.unavailableHint')}
        </Notification>
      ) : null}
      {replaceAttachments.isError ? (
        <Notification tone="error" title={t('lifecycle.evalRun.attachError')}>
          {t('lifecycle.evalRun.attachErrorHint')}
        </Notification>
      ) : null}
      {startRuns.isError ? (
        <Notification tone="error" title={t('lifecycle.evalRun.runError')}>
          {t('lifecycle.evalRun.runErrorHint')}
        </Notification>
      ) : null}
      {live_api && attached.size > 0 && !hasProviderBinding ? (
        <Notification tone="warning" title={t('lifecycle.evalRun.needsProvider')}>
          <span>
            {t('lifecycle.evalRun.needsProviderHint')}{' '}
            <button type="button" className="cursor-pointer font-semibold text-link underline" onClick={() => void navigate(providerBindingEditor)}>
              {t('lifecycle.evalRun.addProvider')}
            </button>
          </span>
        </Notification>
      ) : null}
      {draftDataset.isError ? (
        <Notification tone="error" title={t('lifecycle.evalDatasets.draftError')}>
          {t('lifecycle.evalDatasets.draftErrorHint')}
        </Notification>
      ) : null}
      {deleteNote ? (
        <Notification
          tone="info"
          title={t('lifecycle.evalDatasets.deleted', { name: deleteNote.name })}
          onDismiss={() => setDeleteNote(undefined)}
        >
          {deleteNote.detached > 0
            ? t('lifecycle.evalDatasets.deletedDetached', { count: deleteNote.detached })
            : t('lifecycle.evalDatasets.deletedClean')}
        </Notification>
      ) : null}

      <div
        className={cn(
          'grid items-start gap-4 md:grid-cols-[fit-content(var(--container-drawer))_minmax(0,1fr)]',
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
            onToggle={toggle}
            onCreate={() => setEditor({ mode: 'create' })}
            onDraft={() => setDraftDialogOpen(true)}
            onEdit={(datasetId) => setEditor({ mode: 'edit', datasetId })}
            onCopy={(datasetId) => setEditor({ mode: 'copy', datasetId })}
            onDelete={(dataset) => setPendingDelete(dataset)}
          />
        </div>

        <div className="grid min-w-0 content-start gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-modal border border-border bg-surface px-4 py-3 shadow-panel">
            <div className="grid gap-0.5">
              <h1 className="text-body font-semibold text-ink">{t('lifecycle.evalRun.title')}</h1>
              <p className="text-caption text-muted">{t('lifecycle.evalRun.description')}</p>
            </div>
            <Button
              type="button"
              loading={startRuns.isPending || live}
              disabled={!runnable}
              disabledReason={runDisabledReason}
              leadingIcon={<Play aria-hidden weight="fill" className="size-4" />}
              onClick={() =>
                startRuns.mutate(versionId, {
                  onSuccess: (accepted) => setHandles(accepted.runs),
                })
              }
            >
              {t('lifecycle.evalRun.run', { count: attached.size })}
            </Button>
          </div>

          {handles.length > 0 ? (
            <EvalRunResults reports={reports} />
          ) : (
            <div className="grid place-items-center rounded-modal border border-dashed border-border bg-surface p-10 text-center">
              <p className="text-body text-ink">
                {attached.size === 0
                  ? t('lifecycle.evalRun.pickSomething')
                  : t('lifecycle.evalRun.readyToRun', { count: attached.size })}
              </p>
              <p className="mt-1 max-w-prose text-caption text-muted">
                {t('lifecycle.evalRun.skipIsFine')}
              </p>
            </div>
          )}
        </div>
      </div>

      <BottomActionDock>
        {/* Beside the button that finishes the flow, because the dock is where
            somebody looks for "what now" and going back is one of the two
            answers. Attaching a dataset is a write of its own and is already
            saved, so leaving this way loses nothing. */}
        <Button
          type="button"
          intent="neutral"
          leadingIcon={<ArrowLeft aria-hidden className="size-4" weight="bold" />}
          onClick={() => void navigate(backToEdit)}
        >
          {t('lifecycle.evalRun.backToEdit')}
        </Button>
        <Button type="button" trailingIcon={<ArrowRight aria-hidden className="size-4" weight="bold" />} onClick={() => void navigate(promptDestination)}>{t('lifecycle.evalRun.backToPrompt')}</Button>
      </BottomActionDock>

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
          { versionId: versionId || undefined, folder: promptFolder, brief },
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

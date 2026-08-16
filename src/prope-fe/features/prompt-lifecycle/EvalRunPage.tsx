import { ArrowRight, Play } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import {
  DatasetEditorDialog,
  type DatasetEditorMode,
} from '@/features/prompt-lifecycle/components/DatasetEditorDialog';
import { EvalDatasetTree } from '@/features/prompt-lifecycle/components/EvalDatasetTree';
import { EvalRunResults } from '@/features/prompt-lifecycle/components/EvalRunResults';
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
  promptOptions,
  useDeleteEvalDatasetMutation,
  useDraftEvalDatasetMutation,
  useReplaceDatasetAttachmentsMutation,
  useStartEvalRunsMutation,
} from '@/features/prompt-lifecycle/queries';
import { useEvalRunReports } from '@/features/prompt-lifecycle/useEvalRunReports';

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
  const { promptId = '' } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

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

  const versionId =
    searchParams.get('version') ?? promptQuery.data?.revisions?.[0]?.id ?? '';

  // A run dispatches through provider-access using the revision's own binding,
  // so without one every case comes back a dispatch error and the page reads as
  // a broken prompt. This is the *latest* revision's binding — a revision
  // carries no provider fields in the client model — which is the right one
  // whenever `?version=` came from the composer, and advisory otherwise. The
  // engine is still the authority; this only keeps the button from starting
  // twenty calls that are all going to fail the same way.
  const hasProviderBinding = Boolean(promptQuery.data?.provider && promptQuery.data.providerModel);

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

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-4">
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
        <Notification tone="info" title={t('lifecycle.evalRun.needsProvider')}>
          {t('lifecycle.evalRun.needsProviderHint')}
        </Notification>
      ) : null}
      {handles.length > 0 && live ? (
        <Notification tone="info" title={t('lifecycle.evalRun.inFlight')}>
          {t('lifecycle.evalRun.inFlightHint')}
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

      <div className="grid min-h-dvh gap-4 lg:grid-cols-[minmax(18rem,0.72fr)_minmax(0,2fr)]">
        <div className="min-h-72">
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
            onDraft={() =>
              draftDataset.mutate({
                versionId: versionId || undefined,
                folder: promptFolder,
              })
            }
            onEdit={(datasetId) => setEditor({ mode: 'edit', datasetId })}
            onCopy={(datasetId) => setEditor({ mode: 'copy', datasetId })}
            onDelete={(dataset) => setPendingDelete(dataset)}
          />
        </div>

        <div className="grid min-h-0 content-start gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-modal border border-border bg-surface px-4 py-3 shadow-panel">
            <div className="grid gap-0.5">
              <h1 className="text-body font-semibold text-ink">{t('lifecycle.evalRun.title')}</h1>
              <p className="text-caption text-muted">{t('lifecycle.evalRun.description')}</p>
            </div>
            <Button
              type="button"
              loading={startRuns.isPending || live}
              disabled={!runnable}
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

      <div className="flex justify-end gap-2 sm:sticky sm:bottom-4 sm:z-20">
        <div className="flex gap-2 rounded-full border border-border bg-canvas/95 p-1 shadow-floating backdrop-blur-sm">
          <Button
            type="button"
            intent="ghost"
            onClick={() => void navigate(`/app/prompts/${promptId}`)}
          >
            {t('lifecycle.evalRun.backToPrompt')}
          </Button>
          <Button
            type="button"
            trailingIcon={<ArrowRight aria-hidden className="size-4" weight="bold" />}
            onClick={() => void navigate(`/app/prompts/${promptId}/playground`)}
          >
            {t('lifecycle.evalRun.continue')}
          </Button>
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

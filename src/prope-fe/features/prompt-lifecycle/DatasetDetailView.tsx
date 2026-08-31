import { ArrowLeft, Lock, PencilSimple, Plus, Trash } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Tag } from '@/components/Tag';
import { Notification } from '@/components/Notification';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { DatasetCaseCard } from '@/features/prompt-lifecycle/components/DatasetCaseCard';
import {
  DatasetEditorDialog,
  type DatasetEditorMode,
} from '@/features/prompt-lifecycle/components/DatasetEditorDialog';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { evalDatasetOptions, evalLibraryOptions, useDeleteEvalDatasetMutation } from '@/features/prompt-lifecycle/queries';

interface EditorState { open: boolean; mode: DatasetEditorMode; }

/** The dataset library's detail page: one library set, read whole.
 *
 * The same rows the evaluation workspace ticks, opened up — cases and their
 * assertions on display, with the same editor dialog the workspace tree uses
 * for edit and copy. Builtin sets stay read-only here exactly as they are in
 * the tree: copying one into a folder is the supported way to change it. */
export function DatasetDetailView({ datasetId }: { datasetId?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isNew = !datasetId || datasetId === 'new';

  const query = useQuery({ ...evalDatasetOptions(datasetId ?? ''), enabled: !isNew });
  // Folder slugs in use, offered beside the shared group when copying a set.
  const libraryQuery = useQuery({ ...evalLibraryOptions, enabled: !isNew });
  const removeDataset = useDeleteEvalDatasetMutation();
  const [editor, setEditor] = useState<EditorState>({ open: false, mode: 'create' });
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (!isNew) {
    if (query.isPending) return <QueryState state="loading" />;
    if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  }

  const dataset = query.data;
  const modalityKey = dataset?.output_modality === 'structured' ? 'structured' : 'text';

  return (
    <div className="grid gap-6">
      {isNew ? (
        <>
          <PageIntro
            eyebrow={t('lifecycle.dataset.eyebrow')}
            title={t('lifecycle.dataset.create')}
            description={t('lifecycle.datasetEditor.description')}
          />
          <DatasetEditorDialog
            open
            mode="create"
            defaultFolder=""
            folders={[]}
            onClose={() => void navigate('/app/datasets')}
            onSaved={(saved) => void navigate(`/app/datasets/${encodeURIComponent(saved.dataset_id)}`)}
          />
        </>
      ) : (
        <>
          <button
            type="button"
            onClick={() => void navigate('/app/datasets')}
            className="inline-flex w-fit cursor-pointer items-center gap-1.5 rounded-lg text-caption font-medium text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus"
          >
            <ArrowLeft aria-hidden className="size-4" weight="bold" />
            {t('lifecycle.dataset.detail.back')}
          </button>
          {dataset === undefined ? null : (
            <>
              <PageIntro
                eyebrow={t('lifecycle.dataset.eyebrow')}
                title={dataset.name}
                description={dataset.description}
                action={
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" intent="neutral" leadingIcon={<PencilSimple aria-hidden className="size-4" />} onClick={() => setEditor({ open: true, mode: 'edit' })}>
                      {t('lifecycle.dataset.detail.edit')}
                    </Button>
                    <Button type="button" intent="neutral" leadingIcon={<Plus aria-hidden className="size-4" />} onClick={() => setEditor({ open: true, mode: 'copy' })}>
                      {t('lifecycle.dataset.detail.copy')}
                    </Button>
                    {!dataset.read_only ? (
                      <Button type="button" intent="danger" leadingIcon={<Trash aria-hidden className="size-4" />} onClick={() => setDeleteOpen(true)}>
                        {t('lifecycle.dataset.delete')}
                      </Button>
                    ) : null}
                  </div>
                }
              />
              <div className="flex flex-wrap items-center gap-2">
                <Tag state="neutral">{t(`lifecycle.dataset.types.${dataset.kind.replace('-', '')}`)}</Tag>
                {dataset.tags.map((tag) => <Tag key={tag} state="neutral">{tag}</Tag>)}
                <span className="text-caption text-muted">{t('lifecycle.evalDatasets.caseCount', { count: dataset.case_count })}</span>
                <span className="text-caption text-muted">
                  {t(`lifecycle.dataset.fields.modality.${modalityKey}`)}
                </span>
                {dataset.read_only ? (
                  <span className="inline-flex items-center gap-1 text-caption text-muted">
                    <Lock aria-hidden className="size-3.5" />
                    {t('lifecycle.evalDatasets.readOnly')}
                  </span>
                ) : null}
              </div>
              {dataset.applicability ? (
                <Notification tone="warning" title={t('lifecycle.dataset.fields.applicability')}>
                  {dataset.applicability}
                </Notification>
              ) : null}
              <div className="grid gap-3">
                {dataset.cases.length === 0 ? (
                  <QueryState state="empty" titleOverride={t('lifecycle.dataset.empty.title')} descriptionOverride={t('lifecycle.dataset.empty.body')} />
                ) : (
                  dataset.cases.map((item) => (
                    <DatasetCaseCard key={item.ordinal} item={item} ordinal={item.ordinal} />
                  ))
                )}
              </div>
              <DatasetEditorDialog
                open={editor.open}
                mode={editor.mode}
                datasetId={datasetId}
                defaultFolder={dataset.folder}
                folders={[...new Set([dataset.folder, ...(libraryQuery.data ?? []).map((entry) => entry.folder)])].filter((folder) => folder !== '')}
                onClose={() => setEditor((current) => ({ ...current, open: false }))}
                onSaved={() => setEditor((current) => ({ ...current, open: false }))}
              />
              <Modal
                open={deleteOpen}
                destructive
                title={t('lifecycle.evalDatasets.deleteTitle', { name: dataset.name })}
                description={t('lifecycle.evalDatasets.deleteBody')}
                confirmLabel={t('lifecycle.evalDatasets.deleteConfirm')}
                confirmLoading={removeDataset.isPending}
                onClose={() => setDeleteOpen(false)}
                onConfirm={() => {
                  if (!datasetId) return;
                  removeDataset.mutate(datasetId, {
                    onSuccess: () => {
                      setDeleteOpen(false);
                      void navigate('/app/datasets');
                    },
                  });
                }}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}

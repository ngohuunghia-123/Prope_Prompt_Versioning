import { FloppyDisk, Plus, Trash } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { TagInput } from '@/components/ui/TagInput';
import { Notification } from '@/components/Notification';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { datasetOptions, useDeleteDatasetMutation, useSaveDatasetMutation } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type { DatasetDetail, TestCase } from '@/features/prompt-lifecycle/types';

type DatasetFormValues = { name: string; type: 'golden' | 'regression' | 'red-team'; tags: string[]; description: string; linkedPromptIds: string[] };
type TestCaseFormValues = { name: string; input: string; expectedOutput: string };

function TestCaseRow({ testCase, onEdit, onDelete }: { testCase: TestCase; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="group rounded-lg border border-border bg-subtle p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="grid min-w-0 flex-1 gap-1">
          <h4 className="font-medium text-ink">{testCase.name}</h4>
          <p className="truncate text-caption text-muted">
            <span className="font-medium">Input:</span> {testCase.input}
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button type="button" intent="ghost" onClick={onEdit}>{t('lifecycle.dataset.testCase.edit')}</Button>
          <Button type="button" intent="ghost" leadingIcon={<Trash aria-hidden className="size-4" />} onClick={onDelete} className="text-danger hover:bg-danger/10" />
        </div>
      </div>
      <div className="mt-2 rounded border border-border/50 bg-surface p-2">
        <p className="text-caption text-muted">
          <span className="font-medium">Expected:</span>
        </p>
        <pre className="mt-1 overflow-x-auto text-caption text-ink">{testCase.expectedOutput}</pre>
      </div>
    </div>
  );
}

function TestCaseEditor({ testCase, onSave, onCancel }: { testCase?: TestCase; onSave: (values: TestCaseFormValues) => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const { handleSubmit, register, formState: { errors } } = useForm<TestCaseFormValues>({
    defaultValues: testCase ?? { name: '', input: '', expectedOutput: '' },
  });
  return (
    <div className="rounded-lg border border-focus bg-surface p-4 shadow-panel">
      <h4 className="mb-4 font-semibold text-ink">{testCase ? t('lifecycle.dataset.testCase.edit') : t('lifecycle.dataset.testCase.add')}</h4>
      <form onSubmit={void handleSubmit(onSave)} className="grid gap-4">
        <div>
          <label className="mb-1 block text-caption font-medium text-ink">{t('lifecycle.dataset.testCase.name')}</label>
          <input {...register('name')} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-body shadow-inset outline-none transition-colors focus:border-focus" placeholder={t('lifecycle.dataset.testCase.namePlaceholder')} />
          {errors.name && <p className="mt-1 text-caption text-danger">{t('lifecycle.validation.required')}</p>}
        </div>
        <div>
          <label className="mb-1 block text-caption font-medium text-ink">{t('lifecycle.dataset.testCase.input')}</label>
          <textarea {...register('input')} rows={3} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-body shadow-inset outline-none transition-colors focus:border-focus" placeholder={t('lifecycle.dataset.testCase.inputPlaceholder')} />
          {errors.input && <p className="mt-1 text-caption text-danger">{t('lifecycle.validation.required')}</p>}
        </div>
        <div>
          <label className="mb-1 block text-caption font-medium text-ink">{t('lifecycle.dataset.testCase.expected')}</label>
          <textarea {...register('expectedOutput')} rows={3} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-body font-mono shadow-inset outline-none transition-colors focus:border-focus" placeholder={t('lifecycle.dataset.testCase.expectedPlaceholder')} />
          {errors.expectedOutput && <p className="mt-1 text-caption text-danger">{t('lifecycle.validation.required')}</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" intent="neutral" onClick={onCancel}>{t('lifecycle.dataset.testCase.cancel')}</Button>
          <Button type="submit">{t('lifecycle.dataset.testCase.save')}</Button>
        </div>
      </form>
    </div>
  );
}

function DatasetForm({ dataset, onSave, saving }: { dataset?: DatasetDetail; onSave: (values: DatasetFormValues) => void; saving: boolean }) {
  const { t } = useTranslation();
  const [tags, setTags] = useState(dataset?.tags ?? ['Golden']);
  const { register, handleSubmit, formState: { errors } } = useForm<DatasetFormValues>({
    defaultValues: {
      name: dataset?.name ?? '',
      type: dataset?.type ?? 'golden',
      tags: dataset?.tags ?? ['Golden'],
      description: dataset?.description ?? '',
      linkedPromptIds: dataset?.linkedPromptIds ?? [],
    },
  });
  return (
    <form onSubmit={void handleSubmit((values) => onSave({ ...values, tags }))} className="grid gap-4">
      <div>
        <label className="mb-1 block text-caption font-medium text-ink">{t('lifecycle.dataset.fields.name')}</label>
        <input {...register('name')} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-body shadow-inset outline-none transition-colors focus:border-focus" placeholder={t('lifecycle.dataset.fields.namePlaceholder')} />
        {errors.name && <p className="mt-1 text-caption text-danger">{t('lifecycle.validation.required')}</p>}
      </div>
      <TagInput label={t('lifecycle.dataset.fields.tags')} placeholder={t('lifecycle.dataset.fields.tagsPlaceholder')} addLabel={t('lifecycle.dataset.fields.addTag')} createLabel={(tag) => t('lifecycle.dataset.fields.createTag', { tag })} options={dataset?.tags} values={tags} onChange={setTags} removeLabel={(tag) => t('lifecycle.dataset.fields.removeTag', { tag })} />
      <div>
        <label className="mb-1 block text-caption font-medium text-ink">{t('lifecycle.dataset.fields.description')}</label>
        <textarea {...register('description')} rows={3} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-body shadow-inset outline-none transition-colors focus:border-focus" placeholder={t('lifecycle.dataset.fields.descriptionPlaceholder')} />
      </div>
      <div className="flex justify-end border-t border-border pt-4">
        <Button type="submit" leadingIcon={<FloppyDisk aria-hidden className="size-4" />} loading={saving}>{t('lifecycle.editor.saveDraft')}</Button>
      </div>
    </form>
  );
}

export function DatasetDetailView({ datasetId }: { datasetId?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const isNew = !datasetId || datasetId === 'new';

  const query = useQuery({
    ...datasetOptions(datasetId ?? 'ds_golden_01'),
    enabled: !isNew,
  });

  const saveMutation = useSaveDatasetMutation();
  const deleteMutation = useDeleteDatasetMutation();

  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [editingTestCase, setEditingTestCase] = useState<TestCase | null>(null);
  const [addingTestCase, setAddingTestCase] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [notification, setNotification] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    if (!isNew && query.data && testCases.length === 0) {
      setTestCases(query.data.testCases);
    }
  }, [isNew, query.data, testCases.length]);

  if (!isNew) {
    if (query.isPending) return <QueryState state="loading" />;
    if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  }

  const handleSave = async (values: DatasetFormValues) => {
    try {
      await saveMutation.mutateAsync({ id: isNew ? undefined : datasetId, ...values });
      setNotification({ tone: 'success', message: t('lifecycle.dataset.saveSuccess') });
      if (isNew) {
        setTimeout(() => navigate('/app/datasets'), 800);
      }
    } catch {
      setNotification({ tone: 'error', message: t('lifecycle.dataset.error') });
    }
  };

  const handleDelete = async () => {
    if (!datasetId || datasetId === 'new') return;
    try {
      await deleteMutation.mutateAsync(datasetId);
      navigate('/app/datasets');
    } catch {
      setNotification({ tone: 'error', message: t('lifecycle.dataset.error') });
    }
  };

  const handleAddTestCase = (values: TestCaseFormValues) => {
    const newCase: TestCase = { id: `tc_${Date.now().toString(36)}`, ...values };
    setTestCases((prev) => [...prev, newCase]);
    setAddingTestCase(false);
  };

  const handleEditTestCase = (values: TestCaseFormValues) => {
    if (!editingTestCase) return;
    setTestCases((prev) => prev.map((tc) => tc.id === editingTestCase.id ? { ...tc, ...values } : tc));
    setEditingTestCase(null);
  };

  const handleDeleteTestCase = (id: string) => {
    setTestCases((prev) => prev.filter((tc) => tc.id !== id));
  };

  const dataset = query.data;

  return (
    <div className="grid gap-6">
      {notification && (
        <Notification tone={notification.tone} title={notification.message} onDismiss={() => setNotification(null)}>
          {notification.message}
        </Notification>
      )}
      <PageIntro
        eyebrow={t('lifecycle.dataset.eyebrow')}
        title={isNew ? t('lifecycle.dataset.create') : dataset?.name ?? ''}
        description={isNew ? t('lifecycle.dataset.description') : dataset?.description ?? ''}
        action={
          !isNew && datasetId && datasetId !== 'new' ? (
            <Button type="button" intent="danger" leadingIcon={<Trash aria-hidden className="size-4" />} onClick={() => setDeleteModalOpen(true)}>
              {t('lifecycle.dataset.delete')}
            </Button>
          ) : undefined
        }
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
            <h3 className="mb-4 font-semibold text-ink">{isNew ? t('lifecycle.dataset.create') : t('lifecycle.dataset.edit')}</h3>
            <DatasetForm dataset={dataset} onSave={handleSave} saving={saveMutation.isPending} />
          </div>
          {!isNew && (
            <div className="mt-4 rounded-xl border border-border bg-surface p-4 shadow-panel">
              <p className="text-caption text-muted">{t('lifecycle.dataset.stats.lastUpdated')}</p>
              <p className="mt-1 font-medium text-ink">{format.date(dataset?.updatedAt ?? '')}</p>
            </div>
          )}
        </div>
        <div className="lg:col-span-2">
          <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold text-ink">{t('lifecycle.dataset.fields.testCases')}</h3>
              <Button type="button" leadingIcon={<Plus aria-hidden className="size-4" />} onClick={() => setAddingTestCase(true)}>
                {t('lifecycle.dataset.testCase.add')}
              </Button>
            </div>
            {addingTestCase && (
              <div className="mb-4">
                <TestCaseEditor onSave={handleAddTestCase} onCancel={() => setAddingTestCase(false)} />
              </div>
            )}
            {editingTestCase && (
              <div className="mb-4">
                <TestCaseEditor testCase={editingTestCase} onSave={handleEditTestCase} onCancel={() => setEditingTestCase(null)} />
              </div>
            )}
            {testCases.length === 0 && !addingTestCase ? (
              <p className="py-8 text-center text-caption text-muted">{t('lifecycle.dataset.emptyBody')}</p>
            ) : (
              <div className="grid gap-3">
                {testCases.map((tc) => (
                  <TestCaseRow
                    key={tc.id}
                    testCase={tc}
                    onEdit={() => setEditingTestCase(tc)}
                    onDelete={() => handleDeleteTestCase(tc.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      <Modal
        open={deleteModalOpen}
        title={t('lifecycle.dataset.deleteTitle')}
        description={t('lifecycle.dataset.deleteDescription')}
        confirmLabel={t('lifecycle.dataset.confirmDelete')}
        destructive
        onClose={() => setDeleteModalOpen(false)}
        onConfirm={handleDelete}
      />
    </div>
  );
}

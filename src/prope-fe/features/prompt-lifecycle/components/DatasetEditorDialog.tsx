import { Plus, Trash } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { isApiError } from '@/lib/apiClient';
import {
  ASSERTION_TYPES_BY_MODALITY,
  MAX_CASES_PER_DATASET,
  NUMERIC_ASSERTION_TYPES,
  SHARED_FOLDER,
  type DatasetKind,
  type DatasetWriteInput,
  type EditableAssertionType,
  type EvalDatasetDetail,
} from '@/features/prompt-lifecycle/evalTypes';
import {
  evalDatasetOptions,
  useCreateEvalDatasetMutation,
  useUpdateEvalDatasetMutation,
} from '@/features/prompt-lifecycle/queries';

export type DatasetEditorMode = 'create' | 'edit' | 'copy';

interface DatasetEditorDialogProps {
  open: boolean;
  mode: DatasetEditorMode;
  /** The dataset to edit, or the one to copy. Absent when creating blank. */
  datasetId?: string;
  promptId: string;
  /** Where a new dataset is filed unless the author changes it. */
  defaultFolder: string;
  /** Folder slugs already in use, offered alongside the shared group. */
  folders: string[];
  onClose: () => void;
  onSaved: (dataset: EvalDatasetDetail) => void;
}

interface DraftAssertion {
  key: string;
  type: EditableAssertionType;
  value: string;
}

interface DraftCase {
  key: string;
  name: string;
  input: string;
  assertions: DraftAssertion[];
}

let keySeed = 0;
const nextKey = () => `k${(keySeed += 1)}`;

function blankAssertion(type: EditableAssertionType = 'substring'): DraftAssertion {
  return { key: nextKey(), type, value: '' };
}

function blankCase(): DraftCase {
  return { key: nextKey(), name: '', input: '', assertions: [blankAssertion()] };
}

/** The first user turn. The editor authors single-turn cases; the shipped
 *  catalogue has multi-turn ones and this preserves only the first if one is
 *  opened here — which is why a builtin is copied rather than edited. */
function firstUserContent(messages: Record<string, unknown>[]): string {
  const turn = messages.find((message) => message.role === 'user') ?? messages[0];
  return typeof turn?.content === 'string' ? turn.content : '';
}

function toDrafts(dataset: EvalDatasetDetail): DraftCase[] {
  return dataset.cases.map((entry) => ({
    key: nextKey(),
    name: entry.name,
    input: firstUserContent(entry.input_messages),
    assertions: entry.assertions.map((assertion) => ({
      key: nextKey(),
      type: assertion.type as EditableAssertionType,
      value: assertion.value === null || assertion.value === undefined
        ? ''
        : typeof assertion.value === 'object'
          ? JSON.stringify(assertion.value)
          : String(assertion.value),
    })),
  }));
}

/**
 * The case editor. One dialog, three entry points.
 *
 * **Create**, **copy a shipped set into a folder**, and **edit a workspace
 * set** are the same form because they produce the same thing — a library
 * dataset — and three dialogs would be three places for the assertion rules to
 * drift. Copying is the answer to a shipped set being read-only: the source is
 * loaded, the cases come across, and what gets saved is a new workspace row.
 *
 * **The dialog never touches a suite.** Saving writes to the library; the
 * prompt's yardstick changes only when somebody ticks the set in the tree, and
 * an edit to an already-ticked set reaches a run only at the next run. That is
 * what makes editing safe enough to do in a dialog.
 */
export function DatasetEditorDialog({
  open,
  mode,
  datasetId,
  promptId,
  defaultFolder,
  folders,
  onClose,
  onSaved,
}: DatasetEditorDialogProps) {
  const { t } = useTranslation();

  const sourceQuery = useQuery({
    ...evalDatasetOptions(datasetId ?? ''),
    enabled: open && Boolean(datasetId),
  });

  const createDataset = useCreateEvalDatasetMutation(promptId);
  const updateDataset = useUpdateEvalDatasetMutation(promptId);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [folder, setFolder] = useState(defaultFolder);
  const [kind, setKind] = useState<DatasetKind>('golden');
  const [modality, setModality] = useState<'text' | 'structured'>('text');
  const [cases, setCases] = useState<DraftCase[]>([blankCase()]);
  const [seededFor, setSeededFor] = useState<string>();

  // Seed once per opening, keyed on what is being opened, so typing is not
  // overwritten by a refetch and reopening on a different dataset re-seeds.
  const seedKey = `${open ? 'open' : 'shut'}:${mode}:${datasetId ?? 'blank'}`;
  useEffect(() => {
    if (!open || seededFor === seedKey) return;

    if (!datasetId) {
      setName('');
      setDescription('');
      setFolder(defaultFolder);
      setKind('golden');
      setModality('text');
      setCases([blankCase()]);
      setSeededFor(seedKey);
      return;
    }

    const source = sourceQuery.data;
    if (!source) return;

    setName(mode === 'copy' ? t('lifecycle.datasetEditor.copyName', { name: source.name }) : source.name);
    setDescription(source.description);
    setFolder(mode === 'copy' ? defaultFolder : source.folder);
    setKind(source.kind);
    setModality(source.output_modality);
    setCases(toDrafts(source));
    setSeededFor(seedKey);
  }, [open, seedKey, seededFor, datasetId, mode, defaultFolder, sourceQuery.data, t]);

  useEffect(() => {
    if (!open) setSeededFor(undefined);
  }, [open]);

  const allowedTypes = ASSERTION_TYPES_BY_MODALITY[modality];

  const folderOptions = useMemo(() => {
    const slugs = [...new Set([SHARED_FOLDER, defaultFolder, ...folders])].filter(
      (slug) => slug === SHARED_FOLDER || slug !== '',
    );
    return slugs.map((slug) => ({
      value: slug,
      label: slug === SHARED_FOLDER ? t('lifecycle.evalDatasets.sharedFolder') : slug,
    }));
  }, [defaultFolder, folders, t]);

  const usableCases = cases.filter(
    (entry) =>
      entry.name.trim() !== '' &&
      entry.input.trim() !== '' &&
      entry.assertions.some((assertion) => assertion.value.trim() !== ''),
  );

  const valid = name.trim() !== '' && usableCases.length > 0;
  const saving = createDataset.isPending || updateDataset.isPending;
  const error = createDataset.error ?? updateDataset.error;

  function patchCase(key: string, patch: Partial<DraftCase>) {
    setCases((current) =>
      current.map((entry) => (entry.key === key ? { ...entry, ...patch } : entry)),
    );
  }

  function patchAssertion(caseKey: string, key: string, patch: Partial<DraftAssertion>) {
    setCases((current) =>
      current.map((entry) =>
        entry.key === caseKey
          ? {
              ...entry,
              assertions: entry.assertions.map((assertion) =>
                assertion.key === key ? { ...assertion, ...patch } : assertion,
              ),
            }
          : entry,
      ),
    );
  }

  function body(): DatasetWriteInput {
    return {
      name: name.trim(),
      description: description.trim(),
      kind,
      output_modality: modality,
      folder,
      cases: usableCases.map((entry) => ({
        name: entry.name.trim(),
        input_messages: [{ role: 'user', content: entry.input }],
        input_variables: {},
        assertions: entry.assertions
          .filter((assertion) => assertion.value.trim() !== '')
          .map((assertion) => ({
            type: assertion.type,
            value: NUMERIC_ASSERTION_TYPES.includes(assertion.type)
              ? Number(assertion.value)
              : assertion.type === 'json_schema'
                ? safeJson(assertion.value)
                : assertion.value,
          })),
      })),
    };
  }

  function save() {
    if (!valid) return;
    if (mode === 'edit' && datasetId) {
      updateDataset.mutate(
        { datasetId, body: body() },
        { onSuccess: (saved) => onSaved(saved) },
      );
      return;
    }
    createDataset.mutate(body(), { onSuccess: (saved) => onSaved(saved) });
  }

  return (
    <Modal
      open={open}
      title={t(`lifecycle.datasetEditor.title.${mode}`)}
      description={t('lifecycle.datasetEditor.description')}
      confirmLabel={t('lifecycle.datasetEditor.save')}
      confirmDisabled={!valid}
      confirmLoading={saving}
      onClose={onClose}
      onConfirm={save}
      className="max-w-4xl"
    >
      <div className="grid max-h-[62vh] gap-4 overflow-y-auto pr-1">
        {error ? (
          <p className="rounded-lg bg-danger/10 px-3 py-2 text-caption text-danger-text">
            {isApiError(error) ? error.message : t('lifecycle.datasetEditor.saveError')}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label={t('lifecycle.datasetEditor.name')}
            value={name}
            maxLength={100}
            onChange={(event) => setName(event.currentTarget.value)}
          />
          <Select
            label={t('lifecycle.datasetEditor.folder')}
            options={folderOptions}
            value={folder}
            onValueChange={setFolder}
          />
          <Select
            label={t('lifecycle.datasetEditor.kind')}
            options={(['golden', 'regression', 'red-team'] as DatasetKind[]).map((value) => ({
              value,
              label: t(`lifecycle.dataset.types.${value === 'red-team' ? 'redTeam' : value}`),
            }))}
            value={kind}
            onValueChange={(value) => setKind(value as DatasetKind)}
          />
          <Select
            label={t('lifecycle.datasetEditor.modality')}
            options={[
              { value: 'text', label: t('lifecycle.datasetEditor.modalityText') },
              { value: 'structured', label: t('lifecycle.datasetEditor.modalityStructured') },
            ]}
            value={modality}
            onValueChange={(value) => {
              const next = value as 'text' | 'structured';
              setModality(next);
              // Structured accepts a narrower set of assertion types. Rewriting
              // the now-illegal ones here beats letting the server refuse a save
              // for a rule the form never showed.
              const allowed = ASSERTION_TYPES_BY_MODALITY[next];
              setCases((current) =>
                current.map((entry) => ({
                  ...entry,
                  assertions: entry.assertions.map((assertion) =>
                    allowed.includes(assertion.type)
                      ? assertion
                      : { ...assertion, type: allowed[0] as EditableAssertionType, value: '' },
                  ),
                })),
              );
            }}
          />
        </div>

        <Textarea
          label={t('lifecycle.datasetEditor.datasetDescription')}
          rows={2}
          maxLength={2000}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />

        <div className="grid gap-3">
          {cases.map((entry, index) => (
            <section
              key={entry.key}
              className="grid gap-3 rounded-xl border border-border bg-canvas p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-caption font-semibold text-muted">
                  {t('lifecycle.datasetEditor.caseNumber', { number: index + 1 })}
                </span>
                <Button
                  type="button"
                  intent="ghost"
                  size="navigationIcon"
                  aria-label={t('lifecycle.datasetEditor.removeCase')}
                  disabled={cases.length === 1}
                  onClick={() =>
                    setCases((current) => current.filter((item) => item.key !== entry.key))
                  }
                >
                  <Trash aria-hidden />
                </Button>
              </div>

              <Input
                label={t('lifecycle.datasetEditor.caseName')}
                value={entry.name}
                maxLength={200}
                onChange={(event) => patchCase(entry.key, { name: event.currentTarget.value })}
              />
              <Textarea
                label={t('lifecycle.datasetEditor.caseInput')}
                rows={2}
                value={entry.input}
                onChange={(event) => patchCase(entry.key, { input: event.currentTarget.value })}
              />

              <div className="grid gap-2">
                <span className="text-caption font-semibold text-muted">
                  {t('lifecycle.datasetEditor.assertions')}
                </span>
                {entry.assertions.map((assertion) => (
                  <div
                    key={assertion.key}
                    className="grid grid-cols-[minmax(9rem,0.6fr)_minmax(0,1fr)_auto] items-end gap-2"
                  >
                    <Select
                      label={t('lifecycle.datasetEditor.assertionType')}
                      labelHidden
                      options={allowedTypes.map((type) => ({
                        value: type,
                        label: t(`lifecycle.datasetEditor.assertionTypes.${type}`),
                      }))}
                      value={assertion.type}
                      onValueChange={(value) =>
                        patchAssertion(entry.key, assertion.key, {
                          type: value as EditableAssertionType,
                          value: '',
                        })
                      }
                    />
                    <Input
                      label={t('lifecycle.datasetEditor.assertionValue')}
                      labelHidden
                      placeholder={t(
                        `lifecycle.datasetEditor.assertionPlaceholders.${assertion.type}`,
                      )}
                      inputMode={
                        NUMERIC_ASSERTION_TYPES.includes(assertion.type) ? 'decimal' : undefined
                      }
                      value={assertion.value}
                      onChange={(event) =>
                        patchAssertion(entry.key, assertion.key, {
                          value: event.currentTarget.value,
                        })
                      }
                    />
                    <Button
                      type="button"
                      intent="ghost"
                      size="navigationIcon"
                      aria-label={t('lifecycle.datasetEditor.removeAssertion')}
                      disabled={entry.assertions.length === 1}
                      onClick={() =>
                        patchCase(entry.key, {
                          assertions: entry.assertions.filter(
                            (item) => item.key !== assertion.key,
                          ),
                        })
                      }
                    >
                      <Trash aria-hidden />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  intent="ghost"
                  className="justify-self-start"
                  leadingIcon={<Plus aria-hidden className="size-4" />}
                  onClick={() =>
                    patchCase(entry.key, {
                      assertions: [
                        ...entry.assertions,
                        blankAssertion(allowedTypes[0] as EditableAssertionType),
                      ],
                    })
                  }
                >
                  {t('lifecycle.datasetEditor.addAssertion')}
                </Button>
              </div>
            </section>
          ))}

          <Button
            type="button"
            intent="neutral"
            className="justify-self-start"
            disabled={cases.length >= MAX_CASES_PER_DATASET}
            leadingIcon={<Plus aria-hidden className="size-4" />}
            onClick={() => setCases((current) => [...current, blankCase()])}
          >
            {t('lifecycle.datasetEditor.addCase', { max: MAX_CASES_PER_DATASET })}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** A `json_schema` value the author typed. Invalid JSON goes through as the raw
 *  string so the engine's own refusal is what explains it, rather than the form
 *  silently discarding what was typed. */
function safeJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

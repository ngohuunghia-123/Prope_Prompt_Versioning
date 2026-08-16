import {
  CaretDown,
  Check,
  Copy,
  Lock,
  PencilSimple,
  Plus,
  Sparkle,
  Trash,
  Warning,
} from '@phosphor-icons/react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';
import {
  MAX_ATTACHED_DATASETS,
  SHARED_FOLDER,
  type DatasetKind,
  type EvalDataset,
} from '@/features/prompt-lifecycle/evalTypes';

interface EvalDatasetTreeProps {
  datasets: EvalDataset[];
  attached: Set<string>;
  /** Attached and already run at least once — the tree shows a suite exists. */
  measured: Set<string>;
  /** Attached but the next run would restate the suite rather than reuse it. */
  stale: Set<string>;
  saving: boolean;
  disabled: boolean;
  drafting: boolean;
  onToggle: (datasetId: string, attach: boolean) => void;
  onCreate: () => void;
  onDraft: () => void;
  onEdit: (datasetId: string) => void;
  onCopy: (datasetId: string) => void;
  onDelete: (dataset: EvalDataset) => void;
}

const kindTone: Record<DatasetKind, string> = {
  golden: 'border-success/30 bg-success/15 text-success',
  regression: 'border-warning-strong/30 bg-warning/15 text-warning-text',
  'red-team': 'border-danger/30 bg-danger/15 text-danger',
};

function KindBadge({ kind }: { kind: DatasetKind }) {
  const { t } = useTranslation();
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-caption font-medium',
        kindTone[kind],
      )}
    >
      {t(`lifecycle.dataset.types.${kind === 'red-team' ? 'redTeam' : kind}`)}
    </span>
  );
}

/**
 * The dataset library as a two-level tree: folder, then set.
 *
 * **The tick is the product of this component and running is not.** Ticking
 * records that this prompt has chosen a dataset — one row, no provider call,
 * reversible — and the run button above materialises those choices into suites
 * when somebody asks for evidence. That split is why a set can be chosen while
 * the stack has no credentials configured.
 *
 * The *Chung* group is pinned to the top and never collapsed by default: it
 * holds the shipped read-only sets, which are the only thing a workspace has on
 * its first prompt, and a collapsed empty-looking tree is how somebody
 * concludes there is nothing to evaluate with.
 */
export function EvalDatasetTree({
  datasets,
  attached,
  measured,
  stale,
  saving,
  disabled,
  drafting,
  onToggle,
  onCreate,
  onDraft,
  onEdit,
  onCopy,
  onDelete,
}: EvalDatasetTreeProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const groups = useMemo(() => {
    const byFolder = new Map<string, EvalDataset[]>();
    for (const dataset of datasets) {
      const bucket = byFolder.get(dataset.folder);
      if (bucket) bucket.push(dataset);
      else byFolder.set(dataset.folder, [dataset]);
    }
    for (const bucket of byFolder.values()) {
      bucket.sort((a, b) => a.name.localeCompare(b.name, 'vi'));
    }
    // Chung first whatever the collation says, then the workspace's folders in
    // the order the folder page lists them.
    return [...byFolder.entries()].sort(([a], [b]) => {
      if (a === SHARED_FOLDER) return -1;
      if (b === SHARED_FOLDER) return 1;
      return a.localeCompare(b, 'vi');
    });
  }, [datasets]);

  const atCapacity = attached.size >= MAX_ATTACHED_DATASETS;

  return (
    <aside className="flex min-h-0 flex-col rounded-modal border border-border bg-surface shadow-panel">
      <header className="border-b border-border px-4 py-3">
        <h2 className="text-overline font-bold uppercase tracking-navigation-overline text-muted">
          {t('lifecycle.evalDatasets.title')}
        </h2>
        <p className="mt-1 text-caption text-muted">
          {t('lifecycle.evalDatasets.selected', {
            count: attached.size,
            max: MAX_ATTACHED_DATASETS,
          })}
        </p>
      </header>

      <div className="grid gap-2 border-b border-border p-3">
        <Button
          type="button"
          intent="neutral"
          className="w-full"
          disabled={disabled}
          loading={drafting}
          leadingIcon={<Sparkle aria-hidden weight="fill" className="size-4" />}
          onClick={onDraft}
        >
          {t('lifecycle.evalDatasets.draftWithAi')}
        </Button>
        <Button
          type="button"
          intent="ghost"
          className="w-full"
          disabled={disabled}
          leadingIcon={<Plus aria-hidden className="size-4" />}
          onClick={onCreate}
        >
          {t('lifecycle.evalDatasets.newDataset')}
        </Button>
      </div>

      <div className="min-h-0 grow overflow-y-auto p-2">
        {groups.length === 0 ? (
          <p className="px-2 py-6 text-center text-caption text-muted">
            {t('lifecycle.evalDatasets.empty')}
          </p>
        ) : null}

        {groups.map(([folder, entries]) => {
          const isShared = folder === SHARED_FOLDER;
          const isCollapsed = collapsed[folder] ?? false;
          return (
            <section key={folder || '__shared__'} className="mb-1">
              <button
                type="button"
                onClick={() => setCollapsed((current) => ({ ...current, [folder]: !isCollapsed }))}
                aria-expanded={!isCollapsed}
                className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-caption font-semibold text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"
              >
                <CaretDown
                  aria-hidden
                  weight="bold"
                  className={cn('size-3 shrink-0 transition-transform', isCollapsed && '-rotate-90')}
                />
                <span className="truncate">
                  {isShared ? t('lifecycle.evalDatasets.sharedFolder') : folder}
                </span>
                {isShared ? (
                  <Lock
                    aria-label={t('lifecycle.evalDatasets.readOnly')}
                    weight="fill"
                    className="size-3 shrink-0 text-muted"
                  />
                ) : null}
                <span className="ml-auto shrink-0 text-caption font-normal text-muted">
                  {entries.length}
                </span>
              </button>

              {isCollapsed ? null : (
                <ul className="grid gap-1 py-1">
                  {entries.map((dataset) => {
                    const isAttached = attached.has(dataset.dataset_id);
                    const blocked = disabled || saving || (atCapacity && !isAttached);
                    return (
                      <li
                        key={dataset.dataset_id}
                        className={cn(
                          'group/row rounded-xl border transition-colors',
                          isAttached
                            ? 'border-focus bg-accent-soft'
                            : 'border-transparent hover:bg-subtle',
                        )}
                      >
                        <label
                          className={cn(
                            'grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] gap-2 p-2',
                            blocked && 'cursor-not-allowed opacity-60',
                          )}
                        >
                          <input
                            type="checkbox"
                            className="peer sr-only"
                            checked={isAttached}
                            disabled={blocked}
                            onChange={(event) =>
                              onToggle(dataset.dataset_id, event.currentTarget.checked)
                            }
                          />
                          <span className="mt-0.5 grid size-5 shrink-0 place-items-center self-start rounded border border-border bg-surface shadow-inset transition-colors peer-checked:border-secondary peer-checked:bg-secondary peer-checked:[&>svg]:opacity-100 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus">
                            <Check
                              aria-hidden
                              weight="bold"
                              className="size-3.5 text-inverse opacity-0"
                            />
                          </span>

                          <span className="grid min-w-0 gap-1">
                            <span className="flex items-start justify-between gap-2">
                              <span className="truncate text-body font-medium text-ink">
                                {dataset.name}
                              </span>
                              <KindBadge kind={dataset.kind} />
                            </span>

                            <span className="text-caption text-muted">
                              {t('lifecycle.evalDatasets.caseCount', { count: dataset.case_count })}
                              {measured.has(dataset.dataset_id)
                                ? ` · ${
                                    stale.has(dataset.dataset_id)
                                      ? t('lifecycle.evalDatasets.changedSinceRun')
                                      : t('lifecycle.evalDatasets.alreadyRun')
                                  }`
                                : null}
                            </span>

                            {dataset.applicability ? (
                              <span className="flex items-start gap-1.5 rounded-lg bg-warning/10 px-2 py-1 text-caption text-warning-text">
                                <Warning
                                  aria-hidden
                                  weight="fill"
                                  className="mt-px size-3.5 shrink-0"
                                />
                                <span>{dataset.applicability}</span>
                              </span>
                            ) : null}
                          </span>
                        </label>

                        {/* Outside the label, so pressing an action does not
                            also toggle the tick it sits next to. Revealed on
                            hover and on keyboard focus — three icons on every
                            row would compete with the thing the tree is
                            actually for. */}
                        <div className="flex justify-end gap-0.5 px-1 pb-1 opacity-0 transition-opacity group-hover/row:opacity-100 focus-within:opacity-100">
                          {dataset.read_only ? (
                            <Button
                              type="button"
                              intent="ghost"
                              size="navigationIcon"
                              disabled={disabled}
                              aria-label={t('lifecycle.evalDatasets.copyInto', {
                                name: dataset.name,
                              })}
                              title={t('lifecycle.evalDatasets.copyInto', { name: dataset.name })}
                              onClick={() => onCopy(dataset.dataset_id)}
                            >
                              <Copy aria-hidden />
                            </Button>
                          ) : (
                            <>
                              <Button
                                type="button"
                                intent="ghost"
                                size="navigationIcon"
                                disabled={disabled}
                                aria-label={t('lifecycle.evalDatasets.edit', {
                                  name: dataset.name,
                                })}
                                title={t('lifecycle.evalDatasets.edit', { name: dataset.name })}
                                onClick={() => onEdit(dataset.dataset_id)}
                              >
                                <PencilSimple aria-hidden />
                              </Button>
                              <Button
                                type="button"
                                intent="ghost"
                                size="navigationIcon"
                                disabled={disabled}
                                aria-label={t('lifecycle.evalDatasets.delete', {
                                  name: dataset.name,
                                })}
                                title={t('lifecycle.evalDatasets.delete', { name: dataset.name })}
                                onClick={() => onDelete(dataset)}
                              >
                                <Trash aria-hidden />
                              </Button>
                            </>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}
      </div>

      {atCapacity ? (
        <p className="border-t border-border px-4 py-2 text-caption text-muted">
          {t('lifecycle.evalDatasets.atCapacity', { max: MAX_ATTACHED_DATASETS })}
        </p>
      ) : null}
    </aside>
  );
}

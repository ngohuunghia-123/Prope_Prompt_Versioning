import { CaretDown, Check, Lock, MagnifyingGlass, PencilSimple, Plus, Sparkle, Trash } from '@phosphor-icons/react';
import { useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Tag } from '@/components/Tag';
import { cn } from '@/lib/cn';
import {
  MAX_ATTACHED_DATASETS,
  SHARED_FOLDER,
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
  /** Rendered above the draft/new buttons: the suggest trigger and the run
   * history entry point live in this column too, so the workspace's controls
   * share one place instead of a separate row above the tree. */
  extraActions?: ReactNode;
  /** Draft and new are setup-phase controls: once the revision has results the
   * workspace hides them until the person asks to run a new set again. */
  showManagement?: boolean;
}

function DatasetTags({ tags }: { tags: string[] }) {
  return <span className="flex flex-wrap gap-1">{tags.map((tag) => <Tag key={tag} state="neutral" className="shrink-0">{tag}</Tag>)}</span>;
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
  extraActions,
  showManagement = true,
}: EvalDatasetTreeProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [query, setQuery] = useState('');

  const normalizedQuery = query.trim().toLowerCase();
  const visible = useMemo(() => {
    if (!normalizedQuery) return datasets;
    return datasets.filter(
      (dataset) =>
        dataset.name.toLowerCase().includes(normalizedQuery) ||
        dataset.tags.some((tag) => tag.toLowerCase().includes(normalizedQuery)),
    );
  }, [datasets, normalizedQuery]);

  const groups = useMemo(() => {
    const byFolder = new Map<string, EvalDataset[]>();
    for (const dataset of visible) {
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
  }, [visible]);

  const atCapacity = attached.size >= MAX_ATTACHED_DATASETS;

  return (
    <aside className="flex max-h-[calc(100dvh-18rem)] flex-col rounded-modal border border-border bg-surface shadow-panel navigation:h-full navigation:max-h-none">
      <header className="shrink-0 border-b border-border px-4 py-3">
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

      <div className="grid shrink-0 gap-2 border-b border-border p-3">
        {extraActions}
        {showManagement ? (
          <>
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
          </>
        ) : null}
        <Input
          label={t('lifecycle.evalDatasets.search')}
          labelHidden
          type="search"
          placeholder={t('lifecycle.evalDatasets.searchPlaceholder')}
          leadingIcon={<MagnifyingGlass aria-hidden className="size-4" />}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {/* The scroll area of the panel: with custom datasets the tree outgrows
          the viewport, and the panel scrolls inside itself so the rest of the
          tab — the console, the evidence — stays on screen. */}
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {groups.length === 0 ? (
          <p className="px-2 py-6 text-center text-caption text-muted">
            {normalizedQuery ? t('lifecycle.evalDatasets.searchEmpty') : t('lifecycle.evalDatasets.empty')}
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
                          'group/row relative rounded-xl border transition-colors',
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
                            <span className="flex items-start gap-2">
                              <span className="truncate text-body font-medium text-ink">
                                {dataset.name}
                              </span>
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
                            <DatasetTags tags={dataset.tags} />
                          </span>
                        </label>

                        {/* Outside the label, so pressing an action does not
                            also toggle the tick it sits next to. Revealed on
                            hover and on keyboard focus — three icons on every
                            row would compete with the thing the tree is
                            actually for. */}
                        <div className="absolute right-1 top-1 flex gap-0.5 opacity-0 transition-opacity group-hover/row:opacity-100 focus-within:opacity-100">
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
                              <PencilSimple aria-hidden />
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

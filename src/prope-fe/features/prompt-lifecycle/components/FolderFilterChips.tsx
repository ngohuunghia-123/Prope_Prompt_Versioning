import { MagnifyingGlass, SortAscending, X } from '@phosphor-icons/react';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { EMPTY_FOLDER_FILTERS, type FolderPromptFilters, type FolderPromptSort } from '@/features/prompt-lifecycle/components/folderFilterTypes';
import type { Prompt } from '@/features/prompt-lifecycle/types';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

/** Keystrokes reach the API this long after the last one. */
const SEARCH_DEBOUNCE_MS = 300;

interface FilterChipsProps {
  filters: FolderPromptFilters;
  onFiltersChange: (next: FolderPromptFilters) => void;
  /** Facets read off the folder's unfiltered list — never a hardcoded roster. */
  owners: string[];
  statuses: Prompt['status'][];
  tags: string[];
  resultCount: number;
  /** True while the narrowed list is in flight, so the row can say so. */
  loading?: boolean;
}

export function FolderFilterChips({
  filters,
  onFiltersChange,
  owners,
  statuses,
  tags,
  resultCount,
  loading = false,
}: FilterChipsProps) {
  const { t } = useTranslation();
  const { userName } = useWorkspaceDisplayNames();
  const [searchDraft, setSearchDraft] = useState(filters.search);

  // A chip cleared or a clear-all resets the box from the outside.
  useEffect(() => {
    setSearchDraft(filters.search);
  }, [filters.search]);

  // Typing narrows the list, but only once the typing stops — every commit is a
  // request against the registry's substring search.
  useEffect(() => {
    if (searchDraft === filters.search) return;
    const timer = window.setTimeout(() => {
      onFiltersChange({ ...filters, search: searchDraft });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchDraft, filters, onFiltersChange]);

  const setFilter = useCallback(
    <Key extends keyof FolderPromptFilters>(key: Key, value: FolderPromptFilters[Key]) => {
      onFiltersChange({ ...filters, [key]: value });
    },
    [filters, onFiltersChange],
  );

  const statusOptions = [
    { value: 'all', label: t('lifecycle.folders.detail.filter.allStatus') },
    // Only the statuses this folder actually holds — offering "approved" on a
    // folder with no approved revision would be a filter that answers nothing.
    ...statuses.map((status) => ({ value: status, label: t(`status.${status}`) })),
  ];

  const ownerOptions = [
    { value: 'all', label: t('lifecycle.folders.detail.filter.allOwners') },
    ...owners.map((owner) => ({ value: owner, label: userName(owner) })),
  ];

  const tagOptions = [
    { value: 'all', label: t('lifecycle.folders.detail.filter.allTags') },
    ...tags.map((tag) => ({ value: tag, label: tag })),
  ];

  const sortOptions = [
    { value: 'updated-desc', label: t('lifecycle.folders.detail.sort.updatedDesc') },
    { value: 'updated-asc', label: t('lifecycle.folders.detail.sort.updatedAsc') },
    { value: 'name-asc', label: t('lifecycle.folders.detail.sort.nameAsc') },
    { value: 'name-desc', label: t('lifecycle.folders.detail.sort.nameDesc') },
  ];

  const chips: { key: keyof FolderPromptFilters; label: string; clear: () => void }[] = [];
  if (filters.search.trim() !== '') {
    chips.push({
      key: 'search',
      label: t('lifecycle.folders.detail.filter.chip.search', { value: filters.search.trim() }),
      clear: () => setFilter('search', ''),
    });
  }
  if (filters.status !== 'all') {
    chips.push({
      key: 'status',
      label: t('lifecycle.folders.detail.filter.chip.status', { value: t(`status.${filters.status}`) }),
      clear: () => setFilter('status', 'all'),
    });
  }
  if (filters.owner !== 'all') {
    chips.push({
      key: 'owner',
      label: t('lifecycle.folders.detail.filter.chip.owner', { value: userName(filters.owner) }),
      clear: () => setFilter('owner', 'all'),
    });
  }
  if (filters.tag !== 'all') {
    chips.push({
      key: 'tag',
      label: t('lifecycle.folders.detail.filter.chip.tag', { value: filters.tag }),
      clear: () => setFilter('tag', 'all'),
    });
  }

  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <div className="sm:col-span-2 lg:col-span-2">
          <Input
            label={t('lifecycle.folders.detail.search')}
            labelHidden
            placeholder={t('lifecycle.folders.detail.searchPlaceholder')}
            type="search"
            name="prompt-search"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            leadingIcon={<MagnifyingGlass aria-hidden className="size-4" />}
          />
        </div>
        <Select
          label={t('lifecycle.folders.detail.filter.status')}
          labelHidden
          options={statusOptions}
          selectedLabel={t('lifecycle.folders.detail.filter.statusOption', { value: statusOptions.find((option) => option.value === filters.status)?.label })}
          value={filters.status}
          onValueChange={(value) => setFilter('status', value as FolderPromptFilters['status'])}
        />
        <Select
          label={t('lifecycle.folders.detail.filter.owner')}
          labelHidden
          options={ownerOptions}
          selectedLabel={t('lifecycle.folders.detail.filter.ownerOption', { value: ownerOptions.find((option) => option.value === filters.owner)?.label })}
          value={filters.owner}
          onValueChange={(value) => setFilter('owner', value)}
        />
        <Select
          label={t('lifecycle.folders.detail.filter.tag')}
          labelHidden
          options={tagOptions}
          selectedLabel={t('lifecycle.folders.detail.filter.tagOption', { value: tagOptions.find((option) => option.value === filters.tag)?.label })}
          value={filters.tag}
          onValueChange={(value) => setFilter('tag', value)}
        />
        <Select
          label={t('lifecycle.folders.detail.sort.label')}
          labelHidden
          options={sortOptions}
          selectedLabel={t('lifecycle.folders.detail.sort.option', { value: sortOptions.find((option) => option.value === filters.sort)?.label })}
          value={filters.sort}
          onValueChange={(value) => setFilter('sort', value as FolderPromptSort)}
          leadingIcon={<SortAscending aria-hidden className="size-4" />}
        />
      </div>

      {chips.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2" aria-live="polite">
          <span className="sr-only">{t('lifecycle.folders.detail.filter.active')}</span>
          {chips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={chip.clear}
              aria-label={t('lifecycle.folders.detail.filter.remove', { label: chip.label })}
              className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-subtle px-2.5 py-1.5 text-caption font-normal text-muted shadow-tag transition-colors duration-(--prope-motion-duration-fast) hover:border-focus hover:text-ink"
            >
              <span className="max-w-52 truncate">{chip.label}</span>
              <X aria-hidden weight="bold" className="size-3.5 shrink-0" />
            </button>
          ))}
          <button
            type="button"
            onClick={() => onFiltersChange({ ...EMPTY_FOLDER_FILTERS, sort: filters.sort })}
            className="rounded-control px-2 py-1 text-caption text-muted underline-offset-2 transition-colors duration-(--prope-motion-duration-fast) hover:text-ink hover:underline focus-visible:outline-2 focus-visible:outline-focus"
          >
            {t('lifecycle.folders.detail.filter.clearAll')}
          </button>
          <span className="ml-auto text-caption text-muted">
            {loading
              ? t('lifecycle.folders.detail.filter.filtering')
              : t('lifecycle.folders.detail.filter.resultCount', { count: resultCount })}
          </span>
        </div>
      ) : null}
    </div>
  );
}

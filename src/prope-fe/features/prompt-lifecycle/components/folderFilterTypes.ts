import type { Prompt } from '@/features/prompt-lifecycle/types';

export type FolderPromptSort = 'updated-desc' | 'updated-asc' | 'name-asc' | 'name-desc';

/**
 * What the folder view is currently narrowed to. `search`, `owner` and `tag`
 * travel to `GET /api/v1/prompts` as `q`, `owner_id` and `tag`; `status` and
 * `sort` are applied over the rows that come back, because the registry's own
 * status is `active|retired` and its list order is fixed by the cursor.
 */
export interface FolderPromptFilters {
  readonly search: string;
  readonly status: Prompt['status'] | 'all';
  readonly owner: string;
  readonly tag: string;
  readonly sort: FolderPromptSort;
}

export const EMPTY_FOLDER_FILTERS: FolderPromptFilters = {
  search: '',
  status: 'all',
  owner: 'all',
  tag: 'all',
  sort: 'updated-desc',
};

/** Sort is a view preference, not a filter, so it survives a clear-all. */
export function hasActiveFilters(filters: FolderPromptFilters) {
  return filters.search.trim() !== '' || filters.status !== 'all' || filters.owner !== 'all' || filters.tag !== 'all';
}

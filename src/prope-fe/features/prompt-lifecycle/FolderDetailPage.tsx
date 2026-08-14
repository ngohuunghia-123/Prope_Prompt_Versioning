import { Folder as FolderIcon } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';
import { FolderFilterChips } from '@/features/prompt-lifecycle/components/FolderFilterChips';
import {
  EMPTY_FOLDER_FILTERS,
  hasActiveFilters,
  type FolderPromptFilters,
  type FolderPromptSort,
} from '@/features/prompt-lifecycle/components/folderFilterTypes';
import { PromptTable } from '@/features/prompt-lifecycle/components/PromptTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { folderPromptsOptions, foldersOptions } from '@/features/prompt-lifecycle/queries';
import type { Folder } from '@/features/prompt-lifecycle/folderTypes';
import type { Prompt } from '@/features/prompt-lifecycle/types';

interface StatCardProps {
  label: string;
  value: number;
  variant?: 'default' | 'success' | 'warning' | 'info';
}

function StatCard({ label, value, variant = 'default' }: StatCardProps) {
  const bgClass = {
    default: 'bg-subtle',
    success: 'bg-success/10',
    warning: 'bg-warning/10',
    info: 'bg-info/10',
  }[variant];

  const textClass = {
    default: 'text-ink',
    success: 'text-success-strong',
    warning: 'text-warning-strong',
    info: 'text-info-strong',
  }[variant];

  return (
    <Card className={`flex min-h-28 flex-col gap-1 ${bgClass}`}>
      <span className="text-caption text-muted">{label}</span>
      <span className={`font-display text-heading-1 font-semibold ${textClass}`}>{value}</span>
    </Card>
  );
}

function FolderStatsGrid({ folder }: { folder: Folder }) {
  const { t } = useTranslation();

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label={t('lifecycle.folders.stats.total')} value={folder.promptCount} variant="default" />
      <StatCard label={t('lifecycle.folders.stats.approved')} value={folder.approvedCount} variant="success" />
      <StatCard label={t('lifecycle.folders.stats.inReview')} value={folder.inReviewCount} variant="warning" />
      <StatCard label={t('lifecycle.folders.stats.draft')} value={folder.draftCount} variant="info" />
    </div>
  );
}

function FolderHeader({ folder }: { folder: Folder }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div
          className="flex size-12 items-center justify-center rounded-lg text-white"
          style={{ backgroundColor: folder.color }}
        >
          <FolderIcon aria-hidden className="size-6" weight="duotone" />
        </div>
        <div>
          <p className="text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t('lifecycle.folders.eyebrow')}</p>
          <h1 className="font-display text-heading-1 font-medium text-ink">{folder.name}</h1>
        </div>
      </div>
      <Button
        type="button"
        intent="primary"
        onClick={() => void navigate('/app/prompts/new')}
      >
        {t('lifecycle.folders.detail.newPrompt')}
      </Button>
    </div>
  );
}

const sortComparators: Record<FolderPromptSort, (a: Prompt, b: Prompt) => number> = {
  'updated-desc': (a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
  'updated-asc': (a, b) => Date.parse(a.updatedAt) - Date.parse(b.updatedAt),
  'name-asc': (a, b) => a.title.localeCompare(b.title),
  'name-desc': (a, b) => b.title.localeCompare(a.title),
};

function FolderPromptSection({ folderId }: { folderId: string }) {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<FolderPromptFilters>(EMPTY_FOLDER_FILTERS);

  // The folder's whole list. It is what the owner and tag dropdowns are built
  // from, so their options stay put while a filter narrows the table — and with
  // no filter set it is the same cache entry the narrowed query reads, so the
  // unfiltered view still costs one request.
  const allQuery = useQuery(folderPromptsOptions(folderId));
  const query = useQuery(folderPromptsOptions(folderId, {
    search: filters.search,
    ownerId: filters.owner === 'all' ? undefined : filters.owner,
    tag: filters.tag === 'all' ? undefined : filters.tag,
  }));

  const all = allQuery.data;
  const owners = useMemo(() => [...new Set((all ?? []).map((prompt) => prompt.owner))].sort((a, b) => a.localeCompare(b)), [all]);
  const tags = useMemo(() => [...new Set((all ?? []).flatMap((prompt) => prompt.tags))].sort((a, b) => a.localeCompare(b)), [all]);
  const statuses = useMemo(
    () => [...new Set((all ?? []).map((prompt) => prompt.status))].sort((a, b) => a.localeCompare(b)),
    [all],
  );

  // Status and sort are the half the registry cannot express: its own status is
  // active|retired, and its list order is the cursor's.
  const prompts = useMemo(() => {
    const rows = (query.data ?? []).filter((prompt) => filters.status === 'all' || prompt.status === filters.status);
    return rows.sort(sortComparators[filters.sort]);
  }, [query.data, filters.status, filters.sort]);

  // The bar stays on screen through the loading and error states: a request that
  // failed under a filter is one the reader needs the filter controls to undo.
  return (
    <div className="grid gap-4">
      <FolderFilterChips
        filters={filters}
        onFiltersChange={setFilters}
        owners={owners}
        statuses={statuses}
        tags={tags}
        resultCount={prompts.length}
        loading={query.isFetching}
      />
      {query.isPending ? <QueryState state="loading" /> : null}
      {query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}
      {!query.isPending && !query.isError ? (
        prompts.length > 0 ? (
          <PromptTable prompts={prompts} />
        ) : (
          <QueryState
            state="empty"
            // An empty folder and a filter that matched nothing are different
            // facts, and only one of them is the reader's to fix.
            titleOverride={hasActiveFilters(filters) ? t('lifecycle.folders.detail.filter.noResults.title') : undefined}
            descriptionOverride={hasActiveFilters(filters) ? t('lifecycle.folders.detail.filter.noResults.body') : undefined}
          />
        )
      ) : null}
    </div>
  );
}

/**
 * Renders one folder — a registry namespace — with its header, its derived
 * counts, and the prompts inside it. On the `/prompts` index route there is no
 * `folderId`, and the parent page already draws the workspace stats and folder
 * grid, so this renders nothing.
 */
export function FolderDetailPage() {
  const { folderId } = useParams<{ folderId: string }>();
  const foldersQuery = useQuery({ ...foldersOptions, enabled: folderId !== undefined });

  if (folderId === undefined) {
    return <div className="grid gap-6" />;
  }

  if (foldersQuery.isPending) {
    return <QueryState state="loading" />;
  }

  if (foldersQuery.isError) {
    return <QueryState state="error" onRetry={() => void foldersQuery.refetch()} />;
  }

  const folder = foldersQuery.data?.find((candidate) => candidate.id === folderId);
  if (!folder) {
    return <QueryState state="empty" />;
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-4 border-b border-border pb-6">
        <FolderHeader folder={folder} />
      </div>
      <FolderStatsGrid folder={folder} />
      <FolderPromptSection folderId={folder.id} />
    </div>
  );
}

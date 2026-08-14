import { Folder as FolderIcon } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate, Outlet } from 'react-router-dom';
import { PromptTable } from '@/features/prompt-lifecycle/components/PromptTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { WorkspaceStatsGrid } from '@/features/prompt-lifecycle/components/WorkspaceStatsGrid';
import { foldersOptions, promptsOptions, workspaceStatsOptions } from '@/features/prompt-lifecycle/queries';
import type { Folder } from '@/features/prompt-lifecycle/folderTypes';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

function AllPromptsSection() {
  const { t } = useTranslation();
  const query = useQuery(promptsOptions);
  return (
    <div className="grid gap-4">
      <h2 className="font-display text-heading-2 font-medium text-ink">
        {t('lifecycle.registry.title', { defaultValue: 'Tất cả prompt' })}
      </h2>
      {query.isPending ? (
        <QueryState state="loading" />
      ) : query.isError ? (
        <QueryState state="error" onRetry={() => void query.refetch()} />
      ) : (query.data ?? []).length > 0 ? (
        <PromptTable prompts={query.data ?? []} />
      ) : (
        <QueryState state="empty" />
      )}
    </div>
  );
}

function FolderCard({ folder, onClick }: { folder: Folder; onClick: () => void }) {
  const { t } = useTranslation();
  const { date } = useLocaleFormatters();

  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex flex-col gap-3 rounded-modal border border-border bg-surface p-5 text-left shadow-panel transition-all duration-(--prope-motion-duration-fast) hover:border-primary hover:shadow-card-hover focus-visible:outline-2 focus-visible:outline-focus"
    >
      <div className="flex items-start justify-between gap-3">
        <div
          className="flex size-10 items-center justify-center rounded-lg text-white"
          style={{ backgroundColor: folder.color }}
        >
          <FolderIcon aria-hidden className="size-5" weight="duotone" />
        </div>
        <span className="rounded-full bg-subtle px-2 py-0.5 text-caption text-muted">
          {t('lifecycle.folders.promptCount', { count: folder.promptCount })}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="font-semibold text-ink group-hover:text-primary">{folder.name}</h3>
        <p className="line-clamp-2 text-caption text-muted">{folder.description}</p>
      </div>
      <div className="mt-auto flex items-center justify-between border-t border-border pt-3 text-caption text-muted">
        <span>{t('lifecycle.folders.updatedAt', { date: date(folder.updatedAt) })}</span>
      </div>
    </button>
  );
}

function FolderGrid() {
  const navigate = useNavigate();
  const query = useQuery(foldersOptions);

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const folders = query.data ?? [];
  if (folders.length === 0) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {folders.map((folder) => (
        <FolderCard
          key={folder.id}
          folder={folder}
          onClick={() => void navigate(`/app/prompts/folder/${encodeURIComponent(folder.id)}`)}
        />
      ))}
    </div>
  );
}

export function PromptFoldersPage() {
  const { pathname } = useLocation();
  const workspaceStatsQuery = useQuery(workspaceStatsOptions);

  // Folder slugs are dynamic now, so the folder detail route lives behind a
  // static `folder/` segment — that keeps it unambiguous against
  // /prompts/:promptId without the page having to know the folder list.
  const isFolderDetail = pathname.split('/').filter(Boolean)[2] === 'folder';

  return (
    <>
      {!isFolderDetail && (
        <div className="grid gap-6">
          {workspaceStatsQuery.data ? <WorkspaceStatsGrid stats={workspaceStatsQuery.data} /> : null}

          <FolderGrid />

          <AllPromptsSection />
        </div>
      )}
      <Outlet />
    </>
  );
}

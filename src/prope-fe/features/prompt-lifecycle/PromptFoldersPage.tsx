import { DotsThreeVertical, Folder as FolderIcon, FolderPlus, PencilSimple, Trash } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate, Outlet } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { DeleteFolderDialog } from '@/features/prompt-lifecycle/components/DeleteFolderDialog';
import { FolderFormDialog } from '@/features/prompt-lifecycle/components/FolderFormDialog';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { WorkspaceStatsGrid } from '@/features/prompt-lifecycle/components/WorkspaceStatsGrid';
import { foldersOptions, workspaceStatsOptions } from '@/features/prompt-lifecycle/queries';
import type { Folder } from '@/features/prompt-lifecycle/folderTypes';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { GettingStartedPanel } from '@/features/prompt-lifecycle/components/GettingStartedPanel';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

/**
 * Sửa / Xoá for one card.
 *
 * A hand-rolled popover rather than a shared component because there is no
 * dropdown primitive in `components/ui` yet and this is the first place that
 * wants one — a two-item menu is not enough evidence to design the primitive
 * around. Closes on outside pointer-down and on Escape; the trigger keeps focus
 * so the keyboard path is trigger → menu → back.
 */
function FolderCardMenu({ folder, onEdit, onDelete }: { folder: Folder; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const motion = useMotionPresence(open, 'popover');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  // Deleting is refused while the folder holds anything — the server refuses it
  // too, so this is the affordance telling the truth rather than the guard.
  const deletable = folder.promptCount === 0;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-label={t('lifecycle.folders.menu')}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="grid size-8 place-items-center rounded-full text-muted transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
      >
        <DotsThreeVertical aria-hidden className="size-5" weight="bold" />
      </button>
      {motion.mounted ? (
        <div
          ref={(node) => { motion.surfaceRef.current = node; }}
          role="menu"
          className={cn('absolute right-0 top-9 z-20 flex w-44 flex-col overflow-hidden rounded-lg border border-border bg-surface py-1 shadow-floating', !open && 'pointer-events-none')}
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => { setOpen(false); onEdit(); }}
            className="flex items-center gap-2 px-3 py-2 text-left text-body text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
          >
            <PencilSimple aria-hidden className="size-4" />
            {t('lifecycle.folders.edit')}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={!deletable}
            title={deletable ? undefined : t('lifecycle.folders.deleteBlocked', { count: folder.promptCount })}
            onClick={() => { setOpen(false); onDelete(); }}
            className="flex items-center gap-2 px-3 py-2 text-left text-body text-danger-text hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:text-disabled-text disabled:hover:bg-transparent"
          >
            <Trash aria-hidden className="size-4" />
            {t('lifecycle.folders.delete')}
          </button>
        </div>
      ) : null}
    </div>
  );
}

/**
 * The card is a `div` rather than a `button`, and the title is the link.
 *
 * It used to be one large button covering the whole card, which cannot hold the
 * kebab: a `button` inside a `button` is invalid HTML and browsers recover from
 * it by dropping one of them. So the whole surface stays clickable through an
 * overlay on the title's link, and the menu sits above it on the z-axis.
 */
function FolderCard({ folder, onOpen, onEdit, onDelete }: {
  folder: Folder;
  onOpen: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const { date } = useLocaleFormatters();

  return (
    <div className="group relative flex cursor-pointer flex-col gap-3 rounded-modal border border-border bg-surface p-5 text-left shadow-panel focus-within:border-secondary hover:border-secondary hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-3">
        <div
          className="flex size-10 items-center justify-center rounded-lg text-white"
          style={{ backgroundColor: folder.color }}
        >
          <FolderIcon aria-hidden className="size-5" weight="duotone" />
        </div>
        <div className="relative z-10 flex items-center gap-2">
          <span className="rounded-full bg-subtle px-2 py-0.5 text-caption text-muted">
            {t('lifecycle.folders.promptCount', { count: folder.promptCount })}
          </span>
          <FolderCardMenu folder={folder} onEdit={onEdit} onDelete={onDelete} />
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="font-semibold text-ink group-hover:text-link">
          {/* The stretched link is what keeps the whole card clickable now that
              it is no longer one big button. */}
          <button
            type="button"
            onClick={onOpen}
            className="cursor-pointer text-left after:absolute after:inset-0 after:cursor-pointer after:content-[''] focus-visible:outline-2 focus-visible:outline-focus"
          >
            {folder.name}
          </button>
        </h3>
        <p className="line-clamp-2 text-caption text-muted">{folder.description}</p>
      </div>
      <div className="mt-auto flex items-center justify-between border-t border-border pt-3 text-caption text-muted">
        <span>{t('lifecycle.folders.updatedAt', { date: date(folder.updatedAt) })}</span>
        {/* An observed namespace: prompts sit in it but nobody has named it.
            Editing one is what declares it, which is why the badge is a nudge
            and not a warning. */}
        {folder.declared ? null : (
          <span className="rounded-full bg-subtle px-2 py-0.5">{t('lifecycle.folders.undeclared')}</span>
        )}
      </div>
    </div>
  );
}

function FolderEmptyState({ onCreate }: { onCreate: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-3 rounded-modal border border-dashed border-border bg-surface px-6 py-12 text-center">
      <span aria-hidden className="grid size-12 place-items-center rounded-full bg-subtle text-muted">
        <FolderIcon className="size-6" weight="duotone" />
      </span>
      <h2 className="font-display text-heading-2 font-medium text-ink">{t('lifecycle.folders.empty.title')}</h2>
      <p className="max-w-prose text-body text-muted">{t('lifecycle.folders.empty.body')}</p>
      <Button intent="primary" leadingIcon={<FolderPlus aria-hidden className="size-4" />} onClick={onCreate}>
        {t('lifecycle.folders.empty.action')}
      </Button>
    </div>
  );
}

function FolderGrid() {
  const navigate = useNavigate();
  const query = useQuery(foldersOptions);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Folder | undefined>(undefined);
  const [deleting, setDeleting] = useState<Folder | undefined>(undefined);

  if (query.isPending) return <QueryState state="loading" loadingLayout="cards" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const folders = query.data ?? [];

  return (
    <>
      {/* A brand-new workspace used to render nothing here — stats, then blank
          space — with the only way in being a button in the top bar. */}
      {folders.length === 0 ? (
        <FolderEmptyState onCreate={() => setCreating(true)} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {folders.map((folder) => (
            <FolderCard
              key={folder.id}
              folder={folder}
              onOpen={() => void navigate(`/app/prompts/folder/${encodeURIComponent(folder.id)}`)}
              onEdit={() => setEditing(folder)}
              onDelete={() => setDeleting(folder)}
            />
          ))}
        </div>
      )}

      <FolderFormDialog open={creating} onClose={() => setCreating(false)} />
      <FolderFormDialog
        open={editing !== undefined}
        folder={editing}
        onClose={() => setEditing(undefined)}
      />
      <DeleteFolderDialog folder={deleting} onClose={() => setDeleting(undefined)} />
    </>
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
          <GettingStartedPanel />

          <FolderGrid />
        </div>
      )}
      <Outlet />
    </>
  );
}

import { Buildings, CaretUpDown, Check, Clock } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import { Modal } from '@/components/ui/Modal';
import { Tooltip } from '@/components/ui/Tooltip';
import { lobbyIsLive } from '@/features/auth/lobbyApi';
import { myWorkspacesOptions, useEnterWorkspaceMutation } from '@/features/auth/lobbyQueries';
import { sessionOptions } from '@/features/auth/queries';

/**
 * The way out of a workspace, from inside one.
 *
 * `/workspaces` (ADR-0056) was reachable only by being sent there — a session
 * naming no workspace is redirected to it, and nothing else pointed at it. So a
 * person who belonged to two workspaces could enter the first and then had no
 * route to the second short of signing out. This is that route.
 *
 * **Switching is a server operation, not a client one.** Entering deletes the
 * current session row and mints one naming the target, with a new cookie, so the
 * list here cannot be a link — it is a mutation, and the navigation happens only
 * once it resolves. `useEnterWorkspaceMutation` clears every cached query on the
 * way through, because each one was read under the old tenant.
 *
 * **Pending rows are shown and cannot be entered.** They are the reason somebody
 * opens this menu twice; hiding them until approval would make waiting look like
 * the request never happened.
 */
function useSwitcher() {
  const navigate = useNavigate();
  const live = lobbyIsLive();
  const session = useQuery(sessionOptions);
  const workspaces = useQuery({ ...myWorkspacesOptions, enabled: live });
  const enter = useEnterWorkspaceMutation();

  const memberships = workspaces.data?.items ?? [];
  const currentId = session.data?.user.workspaceId ?? null;

  function open(workspaceId: string, onDone: () => void) {
    if (workspaceId === currentId) return;
    enter.mutate(workspaceId, {
      onSuccess: () => {
        onDone();
        void navigate('/app/prompts', { replace: true });
      },
    });
  }

  return {
    currentId,
    currentName: session.data?.user.workspaceName ?? '',
    enter,
    live,
    navigate,
    active: memberships.filter((membership) => membership.status === 'active'),
    pending: memberships.filter((membership) => membership.status === 'pending'),
    open,
  };
}

interface DialogProps {
  open: boolean;
  onClose: () => void;
  switcher: ReturnType<typeof useSwitcher>;
}

function WorkspaceSwitcherDialog({ open, onClose, switcher }: DialogProps) {
  const { t } = useTranslation();
  const { active, currentId, enter, pending } = switcher;
  return (
    <Modal
      open={open}
      title={t('chooser.switcher.title')}
      description={t('chooser.switcher.description')}
      confirmLabel={t('chooser.switcher.manage')}
      onClose={onClose}
      onConfirm={() => {
        onClose();
        void switcher.navigate('/workspaces');
      }}
      className="max-w-lg"
    >
      <div className="grid gap-3">
        {enter.isError ? (
          <p role="alert" className="text-caption text-danger-text">{t('chooser.enterErrorHint')}</p>
        ) : null}
        {active.length === 0 ? (
          <p className="rounded-modal border border-dashed border-border p-6 text-center text-caption text-muted">
            {t('chooser.switcher.empty')}
          </p>
        ) : (
          <ul className="grid gap-2">
            {active.map((membership) => {
              const current = membership.workspaceId === currentId;
              return (
                <li key={membership.workspaceId}>
                  <button
                    type="button"
                    disabled={current || enter.isPending}
                    aria-current={current || undefined}
                    onClick={() => switcher.open(membership.workspaceId, onClose)}
                    className="flex w-full min-w-0 items-center gap-3 rounded-modal border border-border bg-subtle p-3 text-left transition-colors enabled:cursor-pointer enabled:hover:bg-surface disabled:cursor-default focus-visible:outline-2 focus-visible:outline-focus"
                  >
                    <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-xl bg-surface">
                      <Buildings className="size-5 text-primary" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-body font-medium text-ink">{membership.name}</span>
                      <span className="block truncate font-mono text-caption text-muted">
                        {membership.roles.length === 0 ? t('chooser.yours.noRoles') : membership.roles.join(', ')}
                      </span>
                    </span>
                    {current ? <Check aria-hidden className="size-4 shrink-0 text-success-strong" /> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {pending.length > 0 ? (
          <ul className="grid gap-2">
            {pending.map((membership) => (
              <li
                key={membership.workspaceId}
                className="flex min-w-0 items-center gap-3 rounded-modal border border-dashed border-border p-3"
              >
                <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-xl bg-surface">
                  <Clock className="size-5 text-warning-strong" />
                </span>
                <span className="min-w-0 flex-1 truncate text-body text-muted">{membership.name}</span>
                <StatusBadge tone="pending">{t('chooser.pending.badge')}</StatusBadge>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </Modal>
  );
}

/** The expanded sidebar's row: the workspace you are in, and a way to leave it. */
export function WorkspaceSwitcher() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const switcher = useSwitcher();
  if (!switcher.currentName) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        className="flex min-h-11 w-full min-w-0 cursor-pointer items-center gap-2.5 rounded-navigation-panel bg-canvas p-2.5 text-left text-ink shadow-inset transition-colors hover:bg-surface hover:text-link focus-visible:outline-2 focus-visible:outline-focus"
      >
        <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-lg bg-navigation-avatar">
          <Buildings className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-overline text-muted">{t('chooser.switcher.eyebrow')}</span>
          <span className="block truncate text-navigation-strong font-semibold">{switcher.currentName}</span>
        </span>
        <CaretUpDown aria-hidden className="size-4 shrink-0 text-muted" />
      </button>
      <WorkspaceSwitcherDialog open={open} onClose={() => setOpen(false)} switcher={switcher} />
    </>
  );
}

/** The collapsed rail's icon, opening the same dialog. */
export function WorkspaceCompactSwitcher() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const switcher = useSwitcher();
  if (!switcher.currentName) return null;
  const label = t('chooser.switcher.tooltip', { name: switcher.currentName });
  return (
    <>
      <Tooltip label={label} side="right">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-label={label}
          className="grid size-8 cursor-pointer place-items-center rounded-navigation-control bg-transparent text-navigation-icon transition-colors hover:bg-surface/55 hover:text-navigation-active focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Buildings aria-hidden className="size-navigation-icon-large" />
        </button>
      </Tooltip>
      <WorkspaceSwitcherDialog open={open} onClose={() => setOpen(false)} switcher={switcher} />
    </>
  );
}

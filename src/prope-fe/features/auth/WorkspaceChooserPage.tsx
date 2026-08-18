import { ArrowRight, Buildings, Clock, Plus, SignOut, Ticket } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { lobbyIsLive } from '@/features/auth/lobbyApi';
import {
  myWorkspacesOptions,
  useCreateWorkspaceMutation,
  useEnterWorkspaceMutation,
  useRedeemInviteMutation,
} from '@/features/auth/lobbyQueries';
import { sessionOptions, useLogoutMutation } from '@/features/auth/queries';
import { getLoginPath } from '@/features/auth/returnTo';

/**
 * The screen between signing in and working: which workspace, or a new one.
 *
 * **This is what a session naming no workspace can see** (ADR-0056). Registration
 * no longer creates a workspace, so a brand-new account lands here with an empty
 * list and two ways forward — create one, or redeem a code somebody gave them.
 * The old behaviour minted a workspace named after the person, which meant anybody
 * whose only reason for signing up was to join a colleague owned a junk workspace
 * forever and still had no route to the colleague's.
 *
 * **A pending row is shown and cannot be entered.** Redeeming a code puts the
 * person in a queue an Admin has to act on, and hiding the row until then would
 * make a successful redemption look like nothing happened. Entering is refused by
 * the server — an active membership is the authority — so the button is absent
 * rather than disabled-with-an-explanation.
 *
 * **Entering replaces the session.** The server deletes the current row and mints
 * one naming the target, with a new cookie, because a cross-tenant `UPDATE ... SET
 * workspace_id` is refused by RLS from both sides. So this page navigates only
 * after the mutation resolves, and the mutation clears every cached query — each
 * one was read under the old tenant.
 */
export function WorkspaceChooserPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const live = lobbyIsLive();

  const sessionQuery = useQuery(sessionOptions);
  const workspacesQuery = useQuery({ ...myWorkspacesOptions, enabled: live });

  const enter = useEnterWorkspaceMutation();
  const create = useCreateWorkspaceMutation();
  const redeem = useRedeemInviteMutation();
  const logout = useLogoutMutation();

  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [joined, setJoined] = useState<{ workspaceName: string; status: string }>();

  if (sessionQuery.isPending) {
    return <div className="grid min-h-dvh place-items-center bg-canvas text-body text-muted">{t('common.loading')}</div>;
  }
  if (!sessionQuery.data) return <Navigate to={getLoginPath('/app/prompts')} replace />;

  const memberships = workspacesQuery.data?.items ?? [];
  const active = memberships.filter((membership) => membership.status === 'active');
  const pending = memberships.filter((membership) => membership.status === 'pending');

  function open(workspaceId: string) {
    enter.mutate(workspaceId, { onSuccess: () => void navigate('/app/prompts', { replace: true }) });
  }

  return (
    <main className="min-h-dvh bg-canvas px-4 py-10">
      <div className="mx-auto grid w-full max-w-3xl gap-6">
        <header className="grid gap-2">
          <p className="text-caption font-medium tracking-widest text-muted">{t('chooser.eyebrow')}</p>
          <h1 className="text-h1 text-ink">{t('chooser.title')}</h1>
          <p className="text-body text-muted">
            {t('chooser.description', { name: sessionQuery.data.user.displayName })}
          </p>
        </header>

        {!live ? (
          <Notification tone="info" title={t('chooser.unavailable')}>
            {t('chooser.unavailableHint')}
          </Notification>
        ) : null}

        {enter.isError ? (
          <Notification tone="error" title={t('chooser.enterError')}>
            {t('chooser.enterErrorHint')}
          </Notification>
        ) : null}

        <Card title={t('chooser.yours.title')} description={t('chooser.yours.description')}>
          {workspacesQuery.isPending && live ? (
            <p role="status" className="text-caption text-muted">{t('common.loading')}</p>
          ) : active.length === 0 ? (
            <p className="rounded-modal border border-dashed border-border p-8 text-center text-muted">
              {t('chooser.yours.empty')}
            </p>
          ) : (
            <ul className="grid gap-3">
              {active.map((membership) => (
                <li
                  key={membership.workspaceId}
                  className="flex flex-wrap items-center justify-between gap-4 rounded-modal border border-border bg-subtle p-4"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface">
                      <Buildings className="size-5 text-primary" />
                    </span>
                    <div className="min-w-0 grid gap-0.5">
                      <p className="truncate text-body font-medium text-ink">{membership.name}</p>
                      <p className="truncate font-mono text-caption text-muted">
                        {membership.roles.length === 0
                          ? t('chooser.yours.noRoles')
                          : membership.roles.join(', ')}
                      </p>
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="small"
                    disabled={enter.isPending}
                    trailingIcon={<ArrowRight aria-hidden className="size-4" />}
                    onClick={() => open(membership.workspaceId)}
                  >
                    {t('chooser.yours.open')}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {pending.length > 0 ? (
          <Card title={t('chooser.pending.title')} description={t('chooser.pending.description')}>
            <ul className="grid gap-3">
              {pending.map((membership) => (
                <li
                  key={membership.workspaceId}
                  className="flex flex-wrap items-center justify-between gap-4 rounded-modal border border-border bg-subtle p-4"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface">
                      <Clock className="size-5 text-warning-strong" />
                    </span>
                    <p className="truncate text-body font-medium text-ink">{membership.name}</p>
                  </div>
                  <StatusBadge tone="pending">{t('chooser.pending.badge')}</StatusBadge>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}

        <div className="grid gap-6 md:grid-cols-2">
          <Card title={t('chooser.join.title')} description={t('chooser.join.description')}>
            <div className="grid gap-3">
              {joined ? (
                <Notification
                  tone={joined.status === 'pending' ? 'info' : 'success'}
                  title={
                    joined.status === 'pending'
                      ? t('chooser.join.queued', { name: joined.workspaceName })
                      : t('chooser.join.already', { name: joined.workspaceName })
                  }
                >
                  {joined.status === 'pending' ? t('chooser.join.queuedHint') : t('chooser.join.alreadyHint')}
                </Notification>
              ) : null}
              {redeem.isError ? (
                // One message, because the server answers one refusal: unknown,
                // expired, revoked, exhausted and rate-limited are byte-identical
                // on purpose, and inventing a more specific message here would be
                // inventing information that was withheld deliberately.
                <Notification tone="error" title={t('chooser.join.refused')}>
                  {t('chooser.join.refusedHint')}
                </Notification>
              ) : null}
              <Input
                label={t('chooser.join.codeLabel')}
                hint={t('chooser.join.codeHint')}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                // Case-sensitive: the alphabet is digits and both cases, and
                // folding here would divide the space by 26.
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
              />
              <Button
                type="button"
                disabled={!live || code.trim() === '' || redeem.isPending}
                leadingIcon={<Ticket aria-hidden className="size-4" />}
                onClick={() =>
                  redeem.mutate(code.trim(), {
                    onSuccess: (result) => {
                      setJoined({ workspaceName: result.workspaceName, status: result.status });
                      setCode('');
                    },
                  })
                }
              >
                {t('chooser.join.submit')}
              </Button>
            </div>
          </Card>

          <Card title={t('chooser.create.title')} description={t('chooser.create.description')}>
            <div className="grid gap-3">
              {create.isError ? (
                <Notification tone="error" title={t('chooser.create.refused')}>
                  {t('chooser.create.refusedHint')}
                </Notification>
              ) : null}
              <Input
                label={t('chooser.create.nameLabel')}
                hint={t('chooser.create.nameHint')}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <Button
                type="button"
                disabled={!live || name.trim() === '' || create.isPending}
                leadingIcon={<Plus aria-hidden className="size-4" />}
                onClick={() =>
                  create.mutate(name.trim(), {
                    // Creating does not move the caller into it — that is a
                    // second operation with its own cookie — so the page enters
                    // explicitly once the workspace exists.
                    onSuccess: (created) => {
                      setName('');
                      open(created.workspaceId);
                    },
                  })
                }
              >
                {t('chooser.create.submit')}
              </Button>
            </div>
          </Card>
        </div>

        <div className="justify-self-center">
          <Button
            type="button"
            intent="ghost"
            size="small"
            leadingIcon={<SignOut aria-hidden className="size-4" />}
            onClick={() => logout.mutate(undefined, { onSuccess: () => void navigate(getLoginPath('/app/prompts'), { replace: true }) })}
          >
            {t('auth.logout')}
          </Button>
        </div>
      </div>
    </main>
  );
}

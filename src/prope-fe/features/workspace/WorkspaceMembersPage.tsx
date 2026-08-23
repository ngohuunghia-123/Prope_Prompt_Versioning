import { Check, Copy, Envelope, Plus, Trash, UserCircle, Warning, X } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Tabs } from '@/components/Tabs';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { ContentSkeleton } from '@/components/ui/ContentSkeleton';
import { sessionOptions } from '@/features/auth/queries';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import {
  useApproveMemberMutation,
  useCreateInviteMutation,
  useRejectMemberMutation,
  useRemoveMemberMutation,
  useRevokeInviteMutation,
  useSetMemberRolesMutation,
  workspaceInvitesOptions,
  workspaceMembersOptions,
} from '@/features/workspace/memberQueries';
import { membersAreLive } from '@/features/workspace/membersApi';
import {
  ASSIGNABLE_ROLES,
  type Invite,
  type Member,
  type MemberStatus,
  type WorkspaceRole,
} from '@/features/workspace/memberTypes';

/**
 * Who is in this workspace, who is waiting, and who has been invited.
 *
 * **The pending queue is the screen's reason to exist.** An invitation code
 * admits somebody to a queue and nothing else — `may()` answers a `pending`
 * membership exactly as it answers a `removed` one, so until an Admin presses
 * Approve here the person can reach no prompt, no suite and no run. The badge on
 * the tab is therefore not decoration: it is the count of people who are stuck.
 *
 * **Roles are chosen at approval, not promised by the invitation.** The
 * invitation's roles pre-fill the form and bind nothing, because an hour can pass
 * between creating a code and finding out who used it.
 *
 * **Everything on this page needs `workspace.manage_members`, which only Admin
 * holds.** `Owner` in Prope is a prompt-authoring role: giving it member
 * administration would let any prompt author approve somebody and hand them
 * Admin, which is self-promotion in two clicks. The person who created the
 * workspace already holds Admin.
 */

type Tab = 'members' | 'invitations';

function roleLabel(role: WorkspaceRole): string {
  // Roles stay literal (ADR-0053 rule 9). They are values the API compares.
  return role;
}

function memberTone(status: MemberStatus): 'active' | 'pending' | 'disabled' {
  return status === 'active' ? 'active' : status === 'pending' ? 'pending' : 'disabled';
}

function inviteTone(status: Invite['status']): 'active' | 'pending' | 'disabled' {
  return status === 'live' ? 'active' : status === 'expired' ? 'pending' : 'disabled';
}

export function WorkspaceMembersPage() {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const live = membersAreLive();

  const sessionQuery = useQuery(sessionOptions);
  const workspaceId = sessionQuery.data?.user.workspaceId ?? '';
  const selfId = sessionQuery.data?.user.id ?? '';

  const [tab, setTab] = useState<Tab>('members');
  const [statusFilter, setStatusFilter] = useState<MemberStatus | 'all'>('active');

  const membersQuery = useQuery({
    ...workspaceMembersOptions(workspaceId, statusFilter),
    enabled: live && workspaceId !== '',
  });
  // Its own query rather than a filter over the list above, because the tab badge
  // has to be right on the Members tab too — a count derived from whatever filter
  // happens to be selected would read zero while somebody is waiting.
  const pendingQuery = useQuery({
    ...workspaceMembersOptions(workspaceId, 'pending'),
    enabled: live && workspaceId !== '',
  });
  const invitesQuery = useQuery({
    ...workspaceInvitesOptions(workspaceId),
    enabled: live && workspaceId !== '',
  });

  const approve = useApproveMemberMutation(workspaceId);
  const reject = useRejectMemberMutation(workspaceId);
  const setRoles = useSetMemberRolesMutation(workspaceId);
  const removeMember = useRemoveMemberMutation(workspaceId);
  const createInvite = useCreateInviteMutation(workspaceId);
  const revokeInvite = useRevokeInviteMutation(workspaceId);

  const [approving, setApproving] = useState<Member>();
  const [approvalRoles, setApprovalRoles] = useState<WorkspaceRole[]>([]);
  const [editing, setEditing] = useState<Member>();
  const [editedRoles, setEditedRoles] = useState<WorkspaceRole[]>([]);
  const [pendingRemoval, setPendingRemoval] = useState<Member>();
  const [inviting, setInviting] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRoles, setInviteRoles] = useState<WorkspaceRole[]>([]);
  const [issued, setIssued] = useState<{ code: string | null; email: string | null }>();
  const [copied, setCopied] = useState(false);

  if (sessionQuery.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (sessionQuery.isError) {
    return <QueryState state="error" onRetry={() => void sessionQuery.refetch()} />;
  }

  const pendingCount = pendingQuery.data?.items.length ?? 0;
  const members = membersQuery.data?.items ?? [];
  const invites = invitesQuery.data ?? [];

  async function copyCode(value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function closeInvite() {
    setInviting(false);
    setInviteEmail('');
    setInviteRoles([]);
  }

  function toggle(roles: WorkspaceRole[], role: WorkspaceRole, on: boolean): WorkspaceRole[] {
    return on ? [...roles, role] : roles.filter((held) => held !== role);
  }

  function RoleChecklist({
    selected,
    onChange,
  }: {
    selected: WorkspaceRole[];
    onChange: (roles: WorkspaceRole[]) => void;
  }) {
    return (
      <fieldset className="grid gap-2">
        <legend className="text-body font-medium text-ink">{t('members.roles.label')}</legend>
        <p className="text-caption text-muted">{t('members.roles.hint')}</p>
        <div className="grid gap-1 rounded-lg border border-border p-2">
          {ASSIGNABLE_ROLES.map((role) => (
            <label
              key={role}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-body font-normal text-ink hover:bg-subtle"
            >
              <input
                type="checkbox"
                checked={selected.includes(role)}
                onChange={(event) => onChange(toggle(selected, role, event.target.checked))}
              />
              <span className="font-mono text-caption">{roleLabel(role)}</span>
              <span className="text-caption text-muted">{t(`members.roles.describe.${role}`)}</span>
            </label>
          ))}
        </div>
      </fieldset>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-6">
      <PageIntro
        eyebrow={t('members.page.eyebrow')}
        title={t('members.page.title')}
        description={t('members.page.description')}
      />

      {!live ? (
        <Notification tone="info" title={t('members.page.unavailable')}>
          {t('members.page.unavailableHint')}
        </Notification>
      ) : null}

      {/* The one place a code ever appears. A panel rather than a toast, because
          a toast that disappears takes an unrecoverable secret with it. */}
      {issued ? (
        <Card
          title={
            issued.code
              ? t('members.issued.codeTitle')
              : t('members.issued.emailTitle', { email: issued.email ?? '' })
          }
        >
          {issued.code ? (
            <div className="grid gap-2 rounded-modal border border-warning-strong bg-warning/10 p-4">
              <div className="flex items-start gap-2">
                <Warning aria-hidden weight="fill" className="mt-0.5 size-4 shrink-0 text-warning-text" />
                <p className="text-caption font-medium text-warning-text">{t('members.issued.once')}</p>
              </div>
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-lg bg-ink px-3 py-2 text-center font-mono text-h3 tracking-[0.35em] text-inverse">
                  {issued.code}
                </code>
                <Button
                  type="button"
                  intent="neutral"
                  size="small"
                  leadingIcon={copied ? <Check aria-hidden className="size-4" /> : <Copy aria-hidden className="size-4" />}
                  onClick={() => void copyCode(issued.code ?? '')}
                >
                  {t(copied ? 'members.issued.copied' : 'members.issued.copy')}
                </Button>
              </div>
              <p className="text-caption text-muted">{t('members.issued.approvalNote')}</p>
            </div>
          ) : (
            <p className="text-body text-muted">{t('members.issued.emailBody')}</p>
          )}
          <div className="justify-self-end">
            <Button type="button" intent="ghost" size="small" onClick={() => setIssued(undefined)}>
              {t('members.issued.dismiss')}
            </Button>
          </div>
        </Card>
      ) : null}

      <Tabs
        items={[
          {
            value: 'members',
            label: pendingCount > 0
              ? t('members.tabs.membersWithPending', { count: pendingCount })
              : t('members.tabs.members'),
          },
          { value: 'invitations', label: t('members.tabs.invitations') },
        ]}
        value={tab}
        onValueChange={(value) => setTab(value as Tab)}
        label={t('members.tabs.label')}
      />

      {tab === 'members' ? (
        <Card
          title={t('members.list.title')}
          description={t('members.list.description')}
          action={
            <div className="flex flex-wrap items-center gap-2">
              {(['active', 'pending', 'removed', 'all'] as const).map((value) => (
                <Button
                  key={value}
                  type="button"
                  size="small"
                  intent={statusFilter === value ? 'primary' : 'ghost'}
                  onClick={() => setStatusFilter(value)}
                >
                  {t(`members.filter.${value}`)}
                  {value === 'pending' && pendingCount > 0 ? ` (${pendingCount})` : ''}
                </Button>
              ))}
            </div>
          }
        >
          {membersQuery.isPending && live ? (
            <ContentSkeleton label={t('common.loading')} layout="table" />
          ) : membersQuery.isError ? (
            <QueryState state="error" onRetry={() => void membersQuery.refetch()} />
          ) : members.length === 0 ? (
            <p className="rounded-modal border border-dashed border-border p-8 text-center text-muted">
              {t('members.list.empty')}
            </p>
          ) : (
            <ul className="grid gap-3">
              {members.map((member) => (
                <li
                  key={member.userId}
                  className="flex flex-wrap items-start justify-between gap-4 rounded-modal border border-border bg-subtle p-4"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface">
                      <UserCircle className="size-5 text-primary" />
                    </span>
                    <div className="min-w-0 grid gap-1">
                      <p className="truncate text-body font-medium text-ink">
                        {member.displayName ?? t('members.list.tombstoned')}
                        {member.userId === selfId ? ` · ${t('members.list.you')}` : ''}
                      </p>
                      <p className="truncate text-caption text-muted">
                        {member.email ?? t('members.list.tombstonedEmail')}
                      </p>
                      <p className="text-caption text-muted">
                        {member.roles.length === 0
                          ? t('members.list.noRoles')
                          : member.roles.map(roleLabel).join(', ')}
                        {' · '}
                        {t('members.list.joined', { date: format.date(member.addedAt) })}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge tone={memberTone(member.status)}>
                      {t(`members.status.${member.status}`)}
                    </StatusBadge>
                    {member.status === 'pending' ? (
                      <>
                        <Button
                          type="button"
                          size="small"
                          leadingIcon={<Check aria-hidden className="size-4" />}
                          onClick={() => {
                            setApproving(member);
                            setApprovalRoles([]);
                          }}
                        >
                          {t('members.actions.approve')}
                        </Button>
                        <Button
                          type="button"
                          intent="danger"
                          size="small"
                          leadingIcon={<X aria-hidden className="size-4" />}
                          onClick={() => reject.mutate(member.userId)}
                        >
                          {t('members.actions.reject')}
                        </Button>
                      </>
                    ) : member.status === 'active' ? (
                      <>
                        <Button
                          type="button"
                          intent="neutral"
                          size="small"
                          onClick={() => {
                            setEditing(member);
                            setEditedRoles(member.roles);
                          }}
                        >
                          {t('members.actions.roles')}
                        </Button>
                        <Button
                          type="button"
                          intent="danger"
                          size="small"
                          leadingIcon={<Trash aria-hidden className="size-4" />}
                          onClick={() => setPendingRemoval(member)}
                        >
                          {t('members.actions.remove')}
                        </Button>
                      </>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : (
        <Card
          title={t('members.invites.title')}
          description={t('members.invites.description')}
          action={
            <Button
              type="button"
              size="small"
              disabled={!live}
              leadingIcon={<Plus aria-hidden className="size-4" />}
              onClick={() => setInviting(true)}
            >
              {t('members.invites.create')}
            </Button>
          }
        >
          {invitesQuery.isPending && live ? (
            <ContentSkeleton label={t('common.loading')} layout="table" />
          ) : invitesQuery.isError ? (
            <QueryState state="error" onRetry={() => void invitesQuery.refetch()} />
          ) : invites.length === 0 ? (
            <p className="rounded-modal border border-dashed border-border p-8 text-center text-muted">
              {t('members.invites.empty')}
            </p>
          ) : (
            <ul className="grid gap-3">
              {invites.map((invite) => (
                <li
                  key={invite.inviteId}
                  className="flex flex-wrap items-start justify-between gap-4 rounded-modal border border-border bg-subtle p-4"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface">
                      <Envelope className="size-5 text-primary" />
                    </span>
                    <div className="min-w-0 grid gap-1">
                      <p className="truncate text-body font-medium text-ink">
                        {invite.invitedEmail ?? t('members.invites.codeKind')}
                      </p>
                      <p className="text-caption text-muted">
                        {invite.roles.length === 0
                          ? t('members.invites.decideAtApproval')
                          : invite.roles.map(roleLabel).join(', ')}
                        {' · '}
                        {t('members.invites.expires', { date: format.date(invite.expiresAt) })}
                        {' · '}
                        {invite.maxUses === null
                          ? t('members.invites.usedUnlimited', { count: invite.useCount })
                          : t('members.invites.used', { count: invite.useCount, max: invite.maxUses })}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge tone={inviteTone(invite.status)}>
                      {t(`members.invites.status.${invite.status}`)}
                    </StatusBadge>
                    {invite.status === 'live' ? (
                      <Button
                        type="button"
                        intent="danger"
                        size="small"
                        leadingIcon={<Trash aria-hidden className="size-4" />}
                        onClick={() => revokeInvite.mutate(invite.inviteId)}
                      >
                        {t('members.invites.revoke')}
                      </Button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Modal
        open={approving !== undefined}
        title={t('members.approve.title', { name: approving?.displayName ?? '' })}
        description={t('members.approve.description')}
        confirmLabel={t('members.approve.confirm')}
        confirmLoading={approve.isPending}
        onClose={() => setApproving(undefined)}
        onConfirm={() => {
          if (!approving) return;
          approve.mutate(
            { userId: approving.userId, roles: approvalRoles },
            { onSuccess: () => setApproving(undefined) },
          );
        }}
      >
        <RoleChecklist selected={approvalRoles} onChange={setApprovalRoles} />
      </Modal>

      <Modal
        open={editing !== undefined}
        title={t('members.editRoles.title', { name: editing?.displayName ?? '' })}
        description={t('members.editRoles.description')}
        confirmLabel={t('members.editRoles.confirm')}
        confirmLoading={setRoles.isPending}
        onClose={() => setEditing(undefined)}
        onConfirm={() => {
          if (!editing) return;
          setRoles.mutate(
            { userId: editing.userId, roles: editedRoles },
            { onSuccess: () => setEditing(undefined) },
          );
        }}
      >
        <div className="grid gap-4">
          {setRoles.isError ? (
            <Notification tone="error" title={t('members.editRoles.refused')}>
              {t('members.editRoles.refusedHint')}
            </Notification>
          ) : null}
          <RoleChecklist selected={editedRoles} onChange={setEditedRoles} />
        </div>
      </Modal>

      <Modal
        open={pendingRemoval !== undefined}
        destructive
        title={t('members.remove.title', { name: pendingRemoval?.displayName ?? '' })}
        description={t('members.remove.description')}
        confirmLabel={t('members.remove.confirm')}
        confirmLoading={removeMember.isPending}
        onClose={() => setPendingRemoval(undefined)}
        onConfirm={() => {
          if (!pendingRemoval) return;
          removeMember.mutate(pendingRemoval.userId, {
            onSuccess: () => setPendingRemoval(undefined),
          });
        }}
      />

      <Modal
        open={inviting}
        title={t('members.invite.title')}
        description={t('members.invite.description')}
        confirmLabel={t('members.invite.confirm')}
        confirmLoading={createInvite.isPending}
        onClose={closeInvite}
        onConfirm={() =>
          createInvite.mutate(
            {
              email: inviteEmail.trim() === '' ? undefined : inviteEmail.trim(),
              roles: inviteRoles,
            },
            {
              onSuccess: (created) => {
                setIssued({ code: created.code, email: created.invitedEmail });
                closeInvite();
              },
            },
          )
        }
      >
        <div className="grid gap-4">
          <Input
            label={t('members.invite.emailLabel')}
            hint={t('members.invite.emailHint')}
            value={inviteEmail}
            onChange={(event) => setInviteEmail(event.target.value)}
            type="email"
          />
          <RoleChecklist selected={inviteRoles} onChange={setInviteRoles} />
          <p className="text-caption text-muted">
            {inviteEmail.trim() === ''
              ? t('members.invite.codeExplains')
              : t('members.invite.emailExplains')}
          </p>
        </div>
      </Modal>
    </div>
  );
}

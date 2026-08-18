"""Every write this module makes, each with its history event in one transaction.

**The transaction boundary is the whole point of this file** (A-014, AC-12). Each
command below opens exactly one `workspace_transaction` — or takes the caller's —
and the `append()` call sits inside it. There is no ordering in which the state
change commits and the event does not, and there is no `try` around the append:
`property_history.append` raising fails the whole command, which is how *"a grant
written without its event is a hole in the audit trail"* stops being a thing that
can happen.

**A-117 is enforced at the operation, not reconciled afterwards.** Three commands
can strip the last Admin from a workspace — removing a member, revoking a role,
and replacing a role set — and all three go through :func:`_refuse_if_last_admin`
*before* they write. There is no cross-workspace operator surface to repair a
frozen workspace from and A-012 rules out building one, so the refusal is cheap
and the recovery does not exist.

**Refusals are `ManagementRefusal`, raised here rather than in `api.py`.** A
command that returned a status enum would put the decision *"is this a 404 or a
409"* at every call site, and A-116 makes that decision a security property. The
routes call these and render whatever comes back.
"""

import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.access_control import events, passwords
from prope.access_control.domain import GrantLevel, MemberStatus, Role
from prope.access_control.invites import (
    INVITE_ID_PREFIX,
    INVITE_LIFETIME,
    hash_code,
    mint_invite,
    normalise_code,
)
from prope.access_control.keys import MintedKey, mint_key
from prope.access_control.observability import (
    admin_count,
    grant_total,
    invite_redeem_total,
    key_revoked_total,
    last_admin_refused_total,
)
from prope.access_control.sessions import delete_user_sessions
from prope.db.session import SET_TENANT, invite_lookup_transaction, workspace_transaction
from prope.errors import ErrorCode
from prope.session_auth import ManagementRefusal

__all__ = [
    "USER_ID_PREFIX",
    "WORKSPACE_ID_PREFIX",
    "add_member",
    "approve_member",
    "change_own_password",
    "claim_email_invites",
    "create_api_key",
    "create_code_invite",
    "create_email_invite",
    "create_workspace",
    "derive_workspace_slug",
    "grant_access",
    "redeem_invite",
    "register_account",
    "reject_member",
    "remove_member",
    "revoke_access",
    "revoke_api_key",
    "revoke_invite",
    "set_api_key_scope",
    "set_member_roles",
    "tombstone_user",
]

#: A-045 / ADR-0003. Enforced by `ck_workspace_id_prefix` and `ck_user_id_prefix`
#: so a malformed id is refused by the engine rather than by review.
WORKSPACE_ID_PREFIX = "wsp_"
USER_ID_PREFIX = "usr_"

INSERT_WORKSPACE = text(
    """
    INSERT INTO access.workspace (id, name, slug, created_by, created_at)
    VALUES (:id, :name, :slug, :created_by, :created_at)
    """
)

INSERT_MEMBER = text(
    """
    INSERT INTO access.workspace_member (workspace_id, user_id, added_by, added_at, status)
    VALUES (:workspace_id, :user_id, :added_by, :added_at, 'active')
    ON CONFLICT (workspace_id, user_id) DO NOTHING
    """
)

INSERT_USER = text(
    """
    INSERT INTO access."user" (id, email, display_name, password_hash, must_change_password,
                               status, created_at)
    VALUES (:id, :email, :display_name, :password_hash, true, 'active', :created_at)
    """
)

LOAD_USER_BY_EMAIL = text('SELECT id, status FROM access."user" WHERE email = :email')

#: :func:`register_account`'s insert, and it exists **only** because
#: `INSERT_USER` hard-codes `must_change_password` to `true`.
#:
#: A-110's forced change is about a credential an Admin chose and read out loud;
#: somebody who just typed their own password into a sign-up form is the one case
#: the flag was never about, and setting it there would send them straight from
#: registration to a change-password screen for a password they picked thirty
#: seconds ago. A parameter on `INSERT_USER` was the alternative and is worse: the
#: flag would become something every call site decides, and the site that gets it
#: wrong is the one that hands out a permanent password.
INSERT_SELF_REGISTERED_USER = text(
    """
    INSERT INTO access."user" (id, email, display_name, password_hash, must_change_password,
                               status, created_at)
    VALUES (:id, :email, :display_name, :password_hash, false, 'active', :created_at)
    """
)

INSERT_ROLE_BINDING = text(
    """
    INSERT INTO access.role_binding (workspace_id, user_id, role, granted_by, granted_at)
    VALUES (:workspace_id, :user_id, :role, :granted_by, :granted_at)
    ON CONFLICT (workspace_id, user_id, role) DO NOTHING
    """
)

#: What the person who brings a workspace into existence holds on their first
#: request, at both doors that create one (`create_workspace`, `register_account`).
#:
#: **Admin alone was a dead end.** A-007 gives Admin the workspace — members,
#: releases, ownership transfers — and gives Owner the prompts: `prompt.create`,
#: `revision.create`, `revision.submit` are Owner's and no other role's. A founder
#: bound to Admin only could administer a workspace containing nothing, forever,
#: because the one role that can author is granted by a screen that does not exist
#: yet. The first prompt was unreachable for every self-registered account.
#:
#: **Reviewer is here, and what that costs is written down rather than implied.**
#: It was deliberately excluded until 2026-08-16: NFR-01 separates edit from
#: approve, so a founder who wanted to approve their own first revision had to go
#: and grant themselves Reviewer — a binding another Admin could see. There is no
#: members-and-roles screen, so in practice that meant a hand-written SQL INSERT,
#: and every self-registered account dead-ended at `In review` with a 403.
#:
#: A founder now holds all three, which means one person can author, approve and
#: release. **That is NFR-01's separation dissolved by default**, and it is the
#: real cost: on a workspace that later has more than one member, nothing here
#: re-separates them — the founder keeps Reviewer until somebody removes it.
#:
#: What survives is the property the separation was protecting: self-approval is
#: *recorded*, never silent (A-007's third clause). `approval.self_approved` is
#: set, the review screen says so before the button is pressed, and the history
#: row names the actor. A reader can still tell a one-person release from a
#: two-person one — they simply cannot be prevented.
#:
#: To restore the original posture, drop `Role.REVIEWER` from this tuple and
#: `DELETE FROM access.role_binding WHERE role = 'Reviewer'` for accounts that
#: should not keep it. Nothing else reads this constant.
FOUNDER_ROLES: tuple[Role, ...] = (Role.ADMIN, Role.OWNER, Role.REVIEWER)

DELETE_ROLE_BINDING = text(
    "DELETE FROM access.role_binding WHERE user_id = :user_id AND role = :role"
)

DELETE_ALL_ROLE_BINDINGS = text("DELETE FROM access.role_binding WHERE user_id = :user_id")

LOAD_MEMBER_ROLES = text("SELECT role FROM access.role_binding WHERE user_id = :user_id")

SET_MEMBER_STATUS = text(
    "UPDATE access.workspace_member SET status = :status WHERE user_id = :user_id"
)

LOAD_MEMBER = text(
    """
    SELECT user_id, status
    FROM   access.workspace_member
    WHERE  user_id = :user_id
    """
)

#: A-117's counter, and it joins membership deliberately. A role binding held by
#: somebody whose membership is `removed` is not an Admin anybody can reach, so
#: counting bindings alone would let the last real Admin be removed while the
#: gauge read 1 — the exact state `AccessControlAdminCountZero` exists to prove
#: impossible.
COUNT_ACTIVE_ADMINS = text(
    """
    SELECT count(*)
    FROM   access.role_binding AS rb
    JOIN   access.workspace_member AS wm
      ON   wm.workspace_id = rb.workspace_id AND wm.user_id = rb.user_id
    WHERE  rb.role = 'Admin' AND wm.status = 'active'
    """
)

UPSERT_GRANT = text(
    """
    INSERT INTO access.prompt_grant (workspace_id, prompt_id, grantee_user_id, level,
                                     granted_by, granted_at)
    VALUES (:workspace_id, :prompt_id, :grantee_user_id, :level, :granted_by, :granted_at)
    ON CONFLICT (workspace_id, prompt_id, grantee_user_id) DO UPDATE
        SET level = EXCLUDED.level,
            granted_by = EXCLUDED.granted_by,
            granted_at = EXCLUDED.granted_at
    RETURNING level
    """
)

LOAD_GRANT = text(
    """
    SELECT level
    FROM   access.prompt_grant
    WHERE  prompt_id = :prompt_id AND grantee_user_id = :grantee_user_id
    """
)

DELETE_GRANT = text(
    """
    DELETE FROM access.prompt_grant
    WHERE  prompt_id = :prompt_id AND grantee_user_id = :grantee_user_id
    """
)

DELETE_GRANTS_FOR_USER = text(
    "DELETE FROM access.prompt_grant WHERE grantee_user_id = :grantee_user_id"
)

INSERT_API_KEY = text(
    """
    INSERT INTO access.api_key (id, workspace_id, name, key_hash, last_four,
                                scope_model_names, created_by, created_at)
    VALUES (:id, :workspace_id, :name, :key_hash, :last_four,
            :scope_model_names, :created_by, :created_at)
    """
)

REVOKE_API_KEY = text(
    """
    UPDATE access.api_key
       SET revoked_at = :now
     WHERE id = :key_id AND revoked_at IS NULL
    """
)

#: Replace the scope wholesale, and only on a live key. ``revoked_at IS NULL`` is
#: not defensive tidiness: a revoked key is a closed record of what a credential
#: could reach while it was alive, and re-scoping one would rewrite that record
#: while leaving it just as unusable. The predicate makes it a not-found instead.
#:
#: **The returned array is the stored one, not the supplied one.** The caller
#: echoes what the database now holds, so a caller that de-duplicated differently
#: — or did not — cannot report a scope the gateway will not honour.
SET_API_KEY_SCOPE = text(
    """
    UPDATE access.api_key
       SET scope_model_names = :scope_model_names
     WHERE id = :key_id AND revoked_at IS NULL
    RETURNING scope_model_names
    """
)

#: A-151, as one statement. Every identifying column NULL and every tombstone
#: column set at once — revision 0006's two CHECKs refuse any partial version, so
#: a future edit that dropped a line from this list fails at the engine rather
#: than leaving an account with no name that can still authenticate.
TOMBSTONE_USER = text(
    """
    UPDATE access."user"
       SET email = NULL,
           display_name = NULL,
           password_hash = NULL,
           must_change_password = false,
           status = 'tombstoned',
           tombstoned_at = :now,
           tombstoned_by = :actor_id
     WHERE id = :user_id AND status = 'active'
    """
)

SET_PASSWORD = text(
    """
    UPDATE access."user"
       SET password_hash = :password_hash, must_change_password = false
     WHERE id = :user_id AND status = 'active'
    """
)

LOAD_PASSWORD_HASH = text(
    'SELECT password_hash FROM access."user" WHERE id = :user_id AND status = \'active\''
)

#: One statement for both kinds of invitation (ADR-0057).
#: `ck_workspace_invite_one_kind` refuses a row with both or neither, so the
#: caller passes exactly one non-NULL and the engine is what enforces the choice —
#: two INSERT statements would have made "neither" reachable from a third call
#: site somebody adds later.
INSERT_INVITE = text(
    """
    INSERT INTO access.workspace_invite (id, workspace_id, code_hash, invited_email,
                                         grants_roles, created_by, created_at,
                                         expires_at, max_uses)
    VALUES (:id, :workspace_id, :code_hash, :invited_email,
            :grants_roles, :created_by, :created_at,
            :expires_at, :max_uses)
    """
)

#: The lobby's lookup, run under `invite_lookup_transaction` where the
#: `invite_redeem` policy has already narrowed the table to the presented digest.
#: The `WHERE` is restated anyway: a policy that admits one row and a query that
#: asks for it are two independent statements of the same intent, and the one that
#: would be a security bug if it were missing is the policy.
LOAD_INVITE_BY_CODE = text(
    """
    SELECT id, workspace_id, grants_roles, expires_at, revoked_at, max_uses, use_count
    FROM   access.workspace_invite
    WHERE  code_hash = :code_hash
    """
)

#: Every live seat reserved for one address, oldest first. Not unique: the same
#: person may be expected in two workspaces, and both should land.
LOAD_EMAIL_INVITES = text(
    """
    SELECT id, workspace_id, grants_roles, created_by, expires_at, revoked_at,
           max_uses, use_count
    FROM   access.workspace_invite
    WHERE  invited_email = :invited_email
    ORDER  BY created_at
    """
)

#: Re-read under the workspace's own tenant, with the row locked. The lobby's read
#: happened under a policy keyed on a secret and outside any tenant, so it can say
#: *which* workspace and must not be trusted for *whether it is still live*: two
#: redemptions of the same last remaining use would both pass the first check.
LOAD_INVITE_FOR_UPDATE = text(
    """
    SELECT id, workspace_id, grants_roles, created_by, expires_at, revoked_at,
           max_uses, use_count
    FROM   access.workspace_invite
    WHERE  id = :invite_id
    FOR    UPDATE
    """
)

BUMP_INVITE_USE = text(
    "UPDATE access.workspace_invite SET use_count = use_count + 1 WHERE id = :invite_id"
)

#: Revocation is a timestamp, because revision 0022 withholds `DELETE` — a deleted
#: invitation would orphan the `invite_created` event naming it. `revoked_at IS
#: NULL` makes a second revocation a not-found rather than a rewrite of when the
#: first one happened.
REVOKE_INVITE = text(
    """
    UPDATE access.workspace_invite
       SET revoked_at = :now
     WHERE id = :invite_id AND revoked_at IS NULL
    """
)

#: A pending membership: created by a redemption, and **not** by an administrator.
#: `added_by` names whoever created the invitation rather than the person
#: redeeming it, so the row records who opened the door even before anybody
#: decides to let them through it.
#:
#: `DO NOTHING` rather than an upsert, because the three states it could collide
#: with need three different answers and only one of them is a write — see
#: :func:`redeem_invite`.
INSERT_PENDING_MEMBER = text(
    """
    INSERT INTO access.workspace_member (workspace_id, user_id, added_by, added_at, status)
    VALUES (:workspace_id, :user_id, :added_by, :added_at, 'pending')
    ON CONFLICT (workspace_id, user_id) DO NOTHING
    """
)

LOAD_WORKSPACE_NAME = text("SELECT name FROM access.workspace WHERE id = :workspace_id")

LIST_WORKSPACES = text("SELECT access.list_workspaces()")

LOAD_ANY_MEMBERSHIP = text(
    "SELECT status FROM access.workspace_member WHERE user_id = :user_id"
)


@dataclass(frozen=True, slots=True)
class CreatedWorkspace:
    workspace_id: str
    name: str
    slug: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AddedMember:
    user_id: str
    #: The password an Admin reads out, present only when this call created the
    #: account. Adding an **existing** person to a second workspace does not touch
    #: their credentials, so there is nothing to hand over.
    initial_password: str | None
    roles: tuple[Role, ...]


async def _refuse_if_last_admin(db: AsyncSession, workspace_id: str, *, removing: int) -> None:
    """A-117. Refuse anything that would leave the workspace with zero Admins.

    `removing` is how many active Admin bindings the operation is about to
    destroy. Checked **before** the write rather than reconciled after it: there
    is no operator surface to recover a frozen workspace from, and a workspace
    that reaches zero Admins is permanently stuck — nobody can add a member,
    transfer ownership, rotate a credential or release anything.

    `409` and not `403`. The caller holds `workspace.manage_members`; the
    operation is refused by a rule about the *workspace's* resulting state, not
    by a rule about *them*, and a `403` would send an Admin looking for a
    permission to grant themselves.

    The gauge is refreshed on the way through, so the series
    `AccessControlAdminCountZero` watches is written by the same code path that
    guarantees it can never be zero.
    """
    remaining = int(await db.scalar(COUNT_ACTIVE_ADMINS) or 0)
    admin_count.labels(workspace_id=workspace_id).set(remaining)

    if remaining - removing > 0:
        return

    last_admin_refused_total.inc()
    raise ManagementRefusal(
        status_code=409,
        code=ErrorCode.LAST_ADMIN_CANNOT_BE_REMOVED,
        message="a workspace must always have at least one Admin",
        details={"remaining_admins": remaining},
    )


async def _sync_admin_gauge(db: AsyncSession, workspace_id: str) -> None:
    """Re-read the count after a write, so the gauge reflects committed intent.

    Called at the end of every command that can change it. A gauge only written
    on the refusal path would sit at its last refused value forever, which is a
    number that looks like an invariant holding and is actually a number nobody
    updated.
    """
    admin_count.labels(workspace_id=workspace_id).set(
        int(await db.scalar(COUNT_ACTIVE_ADMINS) or 0)
    )


async def create_workspace(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    actor_id: str,
    name: str,
    slug: str,
    now: datetime,
) -> CreatedWorkspace:
    """The workspace, its creator's membership, their :data:`FOUNDER_ROLES`, and the event.

    **One transaction, and the order is a dependency order rather than a
    preference.** A-109 makes the workspace the tenancy root and A-117 makes an
    Adminless workspace unreachable, so a partial commit here produces exactly the
    frozen state the rest of this file exists to prevent.

    **No `SECURITY DEFINER` function is needed and none is used** (ADR-0042). The
    application generates the identifier, so the transaction sets
    `app.workspace_id` to the id it is *about to* insert and the policy's
    `WITH CHECK` half passes on the row's own terms. That is why `workspace` is
    policied on `id` and why creation is the one write in Prope whose tenant
    context precedes its tenant.
    """
    workspace_id = f"{WORKSPACE_ID_PREFIX}{ULID()}"

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        try:
            await db.execute(
                INSERT_WORKSPACE,
                {
                    "id": workspace_id,
                    "name": name,
                    "slug": slug,
                    "created_by": actor_id,
                    "created_at": now,
                },
            )
        except IntegrityError as error:
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.ALREADY_EXISTS,
                message="a workspace with that slug already exists",
                details={"slug": slug},
            ) from error

        await db.execute(
            INSERT_MEMBER,
            {
                "workspace_id": workspace_id,
                "user_id": actor_id,
                "added_by": actor_id,
                "added_at": now,
            },
        )
        for role in FOUNDER_ROLES:
            await db.execute(
                INSERT_ROLE_BINDING,
                {
                    "workspace_id": workspace_id,
                    "user_id": actor_id,
                    "role": role.value,
                    "granted_by": actor_id,
                    "granted_at": now,
                },
            )
        await events.workspace_created(
            db, workspace_id=workspace_id, actor_id=actor_id, occurred_at=now
        )
        await _sync_admin_gauge(db, workspace_id)

    return CreatedWorkspace(workspace_id=workspace_id, name=name, slug=slug, created_at=now)


@dataclass(frozen=True, slots=True)
class RegisteredAccount:
    """What :func:`register_account` produces. No credential in it, and no workspace.

    The password was the caller's own input, so unlike :class:`AddedMember` there
    is nothing to hand back — which is the difference between somebody choosing a
    password and an Admin issuing one.

    **`workspace_id` and `workspace_name` were removed by ADR-0056**, because
    registration no longer creates one. A brand-new account belongs nowhere and its
    first session is a lobby session; where it goes next is the person's decision,
    made on the chooser, rather than ours made silently in a transaction.
    """

    user_id: str


#: How many random characters are appended to a derived workspace slug.
#:
#: The slug is a unique key, and two people who both call their workspace
#: "Marketing" must both succeed — so a derivation with no entropy would make the
#: second person's sign-up fail with a collision they did not cause and cannot see
#: the cause of. Six base32 characters is roughly 30 bits, which makes a collision
#: something that does not happen rather than something handled.
SLUG_SUFFIX_LENGTH = 6

#: The slug alphabet, and it is `ck_workspace_slug_format`'s rather than this
#: function's taste: `^[a-z0-9][a-z0-9-]{1,62}$`. Vowels are kept — this string is
#: never read aloud, so the usual confusable-character trimming buys nothing.
SLUG_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def derive_workspace_slug(display_name: str) -> str:
    """A legal, unique-enough slug from a person's name. **Never the person's input.**

    `WorkspaceCreate` takes a slug because an Admin creating a second workspace is
    naming something colleagues will read. Sign-up is not that: a slug field on a
    sign-up form is a field whose refusal ("that one is taken") tells a stranger
    what other workspaces exist, which is BR-01's disclosure arriving through a
    door nobody thought of as a read.

    So the slug is derived and salted here, and the person never sees it fail.
    """
    ascii_lowered = [character if character.isalnum() else "-" for character in display_name.lower()]
    stem = "".join(character for character in ascii_lowered if character in f"{SLUG_ALPHABET}-").strip("-")
    # `ck_workspace_slug_format` needs a leading alphanumeric and a length of at
    # least two; a display name of nothing but punctuation would otherwise produce
    # an empty stem and a constraint violation the person cannot act on.
    stem = (stem[:40] or "workspace").lstrip("-") or "workspace"
    suffix = "".join(secrets.choice(SLUG_ALPHABET) for _ in range(SLUG_SUFFIX_LENGTH))
    return f"{stem}-{suffix}"


async def register_account(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    display_name: str,
    email: str,
    password: str,
    now: datetime,
) -> RegisteredAccount:
    """Self-serve sign-up: **a person, and nothing else.**

    **This is the only door into an install with no accounts in it.** Prope has no
    outbound channel (A-071), so every other path to a first user requires a
    session that nothing can issue — `POST /api/v1/workspaces` and
    `POST /workspaces/{id}/members` both authenticate. Until this existed the
    product could be deployed and then not signed into.

    **It stopped creating a workspace with ADR-0056, and that is the point of the
    change rather than a side effect.** Registration used to mint
    `"<display_name>"` as a workspace with the person as Owner, Admin and
    Reviewer, because a session had to name a tenant and a person with no
    membership could not sign in at all. The result was that somebody whose only
    reason for signing up was to join a colleague's workspace got a junk one of
    their own, permanently, and had no route to the colleague's. A session may now
    name no workspace, so the honest answer is to create none and let the person
    choose on the next screen.

    **What it still is: one transaction, and one write.** `access."user"` is global
    and carries no policy (ADR-0045), so this needs no tenant context at all — the
    `workspace_transaction` this function used to open existed only for the
    workspace it no longer creates. `sessionmaker()` with no GUC set can read and
    write that one table and **nothing else**, which is exactly the reach this
    function should have.

    **A taken email is refused, and the disclosure that implies is accepted rather
    than hidden.** Answering `409` tells an unauthenticated stranger that an
    address is registered somewhere in the install — a real enumeration oracle, and
    one that sign-in itself does not have (A-144, ADR-0043). Every alternative is
    worse: pretending to succeed would return a session for an account the caller
    cannot use, and the honest fix — confirm by email — needs the outbound channel
    A-071 refuses. What bounds it is `record_source_failure`: twenty probes per
    address per fifteen minutes, sharing sign-in's window. Recorded as `OQ-139`
    rather than argued away.

    **No history event, and there could not be one.** `history_event.workspace_id`
    is `NOT NULL` and the table is tenant-policied, so an account that belongs to
    no workspace has no trail to be written into — which agrees with A-044 having
    kept authentication facts out of the trail all along. The first event in a
    workspace's life is still `workspace_created`, written by
    :func:`create_workspace` when the person actually makes one.
    """
    user_id = f"{USER_ID_PREFIX}{ULID()}"

    async with sessionmaker() as db:
        async with db.begin():
            try:
                await db.execute(
                    INSERT_SELF_REGISTERED_USER,
                    {
                        "id": user_id,
                        "email": email,
                        "display_name": display_name,
                        "password_hash": passwords.hash_password(password),
                        "created_at": now,
                    },
                )
            except IntegrityError as error:
                # `uq_user_email` is the authority and there is deliberately no
                # read before it: a check-then-insert would answer the same way
                # while losing the race, and the constraint cannot.
                raise ManagementRefusal(
                    status_code=409,
                    code=ErrorCode.EMAIL_ALREADY_REGISTERED,
                    message="that email already belongs to an account",
                ) from error

    # ADR-0057. An Admin may have reserved a seat for this address before it
    # belonged to anybody — that is the whole point of `invited_email`, and this
    # is where the reservation becomes a membership. It runs **after** the user
    # row commits and in its own transactions, because the memberships it writes
    # are tenant-scoped and the insert above is the one write in this module that
    # has no tenant at all.
    #
    # `sign_in` calls it too, so a claim that fails here is retried on the next
    # sign-in rather than lost.
    await claim_email_invites(sessionmaker, user_id=user_id, email=email, now=now)

    return RegisteredAccount(user_id=user_id)


async def add_member(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    email: str,
    display_name: str,
    roles: Iterable[Role],
    now: datetime,
) -> AddedMember:
    """A-110. An Admin creates the account and hands the password over out of band.

    **There is no invitation and no email** (A-071), so the initial password is
    returned in this response and read out by the Admin. `must_change_password`
    defaults to `true` in the column, and `require_session` refuses every route
    but sign-out and change-password until it is cleared — which is what stops
    the handed-over credential becoming the permanent one.

    **An existing person is added rather than refused.** If the email already
    belongs to an active account, this adds a membership for that account and
    returns no password: a person may work in several workspaces, and
    `sessions._sign_in_workspace` is written for exactly that. The disclosure
    this implies — an Admin learns the email is registered somewhere in the
    install — is accepted, and it is bounded by who can reach the route: the
    caller already holds `workspace.manage_members`, and refusing instead would
    make multi-workspace membership unreachable through the API.

    **A tombstoned email cannot be reused.** The column is NULL on those rows, so
    the lookup below simply does not find them, and the id stays reserved
    (ADR-0054) — which is the whole reason the row is kept rather than deleted.
    """
    existing = (await db.execute(LOAD_USER_BY_EMAIL, {"email": email})).one_or_none()

    if existing is None:
        user_id = f"{USER_ID_PREFIX}{ULID()}"
        initial_password = passwords_initial()
        try:
            await db.execute(
                INSERT_USER,
                {
                    "id": user_id,
                    "email": email,
                    "display_name": display_name,
                    "password_hash": passwords.hash_password(initial_password),
                    "created_at": now,
                },
            )
        except IntegrityError as error:
            # Lost the race with a concurrent add of the same email. The unique
            # index is the authority; the read above is an optimisation.
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.EMAIL_ALREADY_REGISTERED,
                message="that email already belongs to an account",
            ) from error
    else:
        user_id = existing.id
        initial_password = None

    already = (await db.execute(LOAD_MEMBER, {"user_id": user_id})).one_or_none()
    if already is not None and already.status == MemberStatus.ACTIVE.value:
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.ALREADY_EXISTS,
            message="that person is already a member of this workspace",
        )

    await db.execute(
        INSERT_MEMBER,
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "added_by": actor_id,
            "added_at": now,
        },
    )
    # A re-add of somebody previously removed: the row is retained (A-151), so
    # INSERT ... DO NOTHING left it alone and the status has to be lifted.
    await db.execute(SET_MEMBER_STATUS, {"status": MemberStatus.ACTIVE.value, "user_id": user_id})

    assigned = tuple(roles)
    for role in assigned:
        await db.execute(
            INSERT_ROLE_BINDING,
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "role": role.value,
                "granted_by": actor_id,
                "granted_at": now,
            },
        )

    await events.member_added(
        db, workspace_id=workspace_id, actor_id=actor_id, user_id=user_id, occurred_at=now
    )
    for role in assigned:
        await events.role_assigned(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            user_id=user_id,
            role=role,
            occurred_at=now,
        )

    await _sync_admin_gauge(db, workspace_id)
    return AddedMember(user_id=user_id, initial_password=initial_password, roles=assigned)


def passwords_initial() -> str:
    """A handed-over password: high-entropy, and replaced at first sign-in.

    Generated rather than accepted from the Admin. An Admin-chosen initial
    password is an Admin-chosen *pattern* across every account they create, and
    the pattern outlives the accounts that were supposed to change it — which is
    the failure `must_change_password` alone does not prevent.
    """
    return secrets.token_urlsafe(12)


async def remove_member(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    now: datetime,
) -> None:
    """Move a membership to `removed`, drop its role bindings, write one event.

    **The row is retained** (A-151): it is how a tombstone later knows which
    workspaces to write its event into, and revision 0006 withholds `DELETE` on
    the table so the retention is a privilege rather than a habit.

    **The role bindings are deleted and produce no `role_revoked` events.** One
    departure is one fact, and emitting an event per binding would record it two
    to five times in a trail somebody has to read. `member_removed` is the fact;
    the bindings going with it is what "removed" means.

    **Effective immediately, mid-task, and that is correct** (ADR-0022). Their
    next action fails with no warning, which is a genuinely bad experience and
    the alternative is a window in which a removed member still acts. The refusal
    shape does the work of making it survivable (A-116).
    """
    member = (await db.execute(LOAD_MEMBER, {"user_id": user_id})).one_or_none()
    if member is None or member.status != MemberStatus.ACTIVE.value:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such member",
        )

    held = {row for row in (await db.execute(LOAD_MEMBER_ROLES, {"user_id": user_id})).scalars()}
    await _refuse_if_last_admin(db, workspace_id, removing=1 if Role.ADMIN.value in held else 0)

    await db.execute(DELETE_ALL_ROLE_BINDINGS, {"user_id": user_id})
    await db.execute(SET_MEMBER_STATUS, {"status": MemberStatus.REMOVED.value, "user_id": user_id})
    # Their sessions in THIS workspace end with the membership. A session is
    # workspace-scoped (it carries one), so a person removed from one workspace
    # keeps working in another — which is the behaviour a multi-workspace
    # membership implies and the reason this is not `delete_user_sessions`
    # across the install.
    await delete_user_sessions(db, user_id)

    await events.member_removed(
        db, workspace_id=workspace_id, actor_id=actor_id, user_id=user_id, occurred_at=now
    )
    await _sync_admin_gauge(db, workspace_id)


async def set_member_roles(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    roles: Iterable[Role],
    now: datetime,
) -> tuple[Role, ...]:
    """Replace a member's role set, emitting one event per role actually changed.

    **A `PUT` of the whole set rather than a patch of one role**, for
    `SpendCeilingSet`'s reason one module over: with a partial update, *"I did not
    mention Admin"* and *"I want Admin removed"* are indistinguishable. The diff
    below is what turns a declarative set into the pair of event streams A-014
    wants — and it is why an idempotent `PUT` of the same set writes **no**
    events at all, which is the correct trail for an operation that changed
    nothing.
    """
    member = (await db.execute(LOAD_MEMBER, {"user_id": user_id})).one_or_none()
    if member is None or member.status != MemberStatus.ACTIVE.value:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such member",
        )

    held = {
        Role(row) for row in (await db.execute(LOAD_MEMBER_ROLES, {"user_id": user_id})).scalars()
    }
    wanted = set(roles)

    losing_admin = Role.ADMIN in held and Role.ADMIN not in wanted
    await _refuse_if_last_admin(db, workspace_id, removing=1 if losing_admin else 0)

    for role in sorted(wanted - held, key=lambda member_role: member_role.value):
        await db.execute(
            INSERT_ROLE_BINDING,
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "role": role.value,
                "granted_by": actor_id,
                "granted_at": now,
            },
        )
        await events.role_assigned(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            user_id=user_id,
            role=role,
            occurred_at=now,
        )

    for role in sorted(held - wanted, key=lambda member_role: member_role.value):
        await db.execute(DELETE_ROLE_BINDING, {"user_id": user_id, "role": role.value})
        await events.role_revoked(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            user_id=user_id,
            role=role,
            occurred_at=now,
        )

    await _sync_admin_gauge(db, workspace_id)
    return tuple(sorted(wanted, key=lambda member_role: member_role.value))


# ---------------------------------------------------------------------------
# Invitations and the pending queue — ADR-0057
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreatedInvite:
    """What an invitation write hands back. `code` is present **once**, or never.

    A code invitation returns its plaintext in this object and in exactly one
    response body; an email invitation has no code at all, so the field is `None`
    and there is nothing to hand over. The two kinds are one row and one dataclass
    because they differ in exactly one column — see `INSERT_INVITE`.
    """

    invite_id: str
    code: str | None
    invited_email: str | None
    grants_roles: tuple[Role, ...]
    created_at: datetime
    expires_at: datetime
    max_uses: int | None


@dataclass(frozen=True, slots=True)
class RedeemedInvite:
    """Where a redemption landed, and in what state.

    `status` is `PENDING` for a code that was accepted, and `ACTIVE` when the
    person turns out to be a member already. Both are successes: re-presenting a
    code you have already redeemed must not be an error, or a person who reloads
    the page sees a failure for something that worked.
    """

    workspace_id: str
    workspace_name: str
    status: MemberStatus


def _invite_is_live(row, now: datetime) -> bool:
    """Revoked, expired, exhausted — one predicate, and one refusal for all three.

    The caller never learns which. `ErrorCode.INVITE_NOT_REDEEMABLE` is the answer
    for a code that never existed as well, so a guesser cannot use the refusal to
    tell *"wrong code"* from *"right code, an hour too late"* — the second would
    confirm that a workspace exists behind that string and turn the search into a
    two-phase one.
    """
    if row.revoked_at is not None or row.expires_at <= now:
        return False
    return row.max_uses is None or row.use_count < row.max_uses


def _not_redeemable() -> ManagementRefusal:
    """The one refusal every redemption failure shares. 404, not 403.

    Forbidden would say *"this is a real invitation and you may not use it"*,
    which is the disclosure the single code exists to avoid. Not-found says
    nothing about whether the string was ever an invitation.
    """
    return ManagementRefusal(
        status_code=404,
        code=ErrorCode.INVITE_NOT_REDEEMABLE,
        message="that invitation cannot be redeemed",
    )


async def create_code_invite(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    roles: Iterable[Role],
    now: datetime,
    max_uses: int | None = None,
) -> CreatedInvite:
    """Mint a code, store its digest, record the event. **The code is returned once.**

    `roles` is what the approval screen will pre-select and **not** what the
    redeemer receives: a code invitation always lands in the pending queue, and an
    Admin picks the roles at approval (:func:`approve_member`). Storing the
    intention anyway is what makes the pre-fill honest — the Admin who created the
    code said what it was for, and the Admin who approves sees it.

    `max_uses` of `None` is unlimited **within the hour**, which is safe for the
    same reason: every redemption is a knock, not an entry.
    """
    minted = mint_invite()
    assigned = tuple(roles)
    expires_at = now + INVITE_LIFETIME

    await db.execute(
        INSERT_INVITE,
        {
            "id": minted.invite_id,
            "workspace_id": workspace_id,
            "code_hash": minted.code_hash,
            "invited_email": None,
            "grants_roles": [role.value for role in assigned],
            "created_by": actor_id,
            "created_at": now,
            "expires_at": expires_at,
            "max_uses": max_uses,
        },
    )
    await events.invite_created(
        db, workspace_id=workspace_id, actor_id=actor_id, invite_id=minted.invite_id, occurred_at=now
    )

    return CreatedInvite(
        invite_id=minted.invite_id,
        code=minted.code,
        invited_email=None,
        grants_roles=assigned,
        created_at=now,
        expires_at=expires_at,
        max_uses=max_uses,
    )


async def create_email_invite(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    email: str,
    roles: Iterable[Role],
    now: datetime,
) -> CreatedInvite:
    """Reserve a seat for an address, whether or not anybody holds it yet.

    **This is the row that lets an Admin invite somebody who has no account.** A
    membership cannot exist before its user does — `workspace_member.user_id` is a
    foreign key to `access."user"` — so the reservation lives on the invitation
    and is claimed by :func:`claim_email_invites` the first time that address signs
    in or registers.

    **It grants outright, unlike a code.** An email invitation is an administrator
    naming a specific person, which is the same decision `add_member` makes; the
    pending queue exists for the case where the workspace does *not* know who is
    knocking. So `roles` here are bound at claim time and the person is `active`
    immediately.

    **The address is stored lower-cased**, and it is the one place in this module
    that normalises an email. `access."user".email` keeps what the person typed
    (`LoginRequest` explains why the limiter needs that), so matching the two
    exactly would miss an Admin who typed `Bob@` for somebody who registered
    `bob@`. Both sides of *this* comparison are folded, and the user row is
    untouched.

    `max_uses` is 1 and not configurable: the row names one person.
    """
    invite_id = f"{INVITE_ID_PREFIX}{ULID()}"
    assigned = tuple(roles)
    expires_at = now + INVITE_LIFETIME

    await db.execute(
        INSERT_INVITE,
        {
            "id": invite_id,
            "workspace_id": workspace_id,
            "code_hash": None,
            "invited_email": email.strip().lower(),
            "grants_roles": [role.value for role in assigned],
            "created_by": actor_id,
            "created_at": now,
            "expires_at": expires_at,
            "max_uses": 1,
        },
    )
    await events.invite_created(
        db, workspace_id=workspace_id, actor_id=actor_id, invite_id=invite_id, occurred_at=now
    )

    return CreatedInvite(
        invite_id=invite_id,
        code=None,
        invited_email=email.strip().lower(),
        grants_roles=assigned,
        created_at=now,
        expires_at=expires_at,
        max_uses=1,
    )


async def revoke_invite(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    invite_id: str,
    now: datetime,
) -> None:
    """Close an invitation early. Idempotence is deliberately **not** offered.

    A second revocation is a not-found, because the alternative — answering `204`
    and writing a second `invite_revoked` — would put two events in the trail for
    one act and rewrite when the first one happened.
    """
    revoked = await db.execute(REVOKE_INVITE, {"invite_id": invite_id, "now": now})
    if revoked.rowcount == 0:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such invitation",
        )

    await events.invite_revoked(
        db, workspace_id=workspace_id, actor_id=actor_id, invite_id=invite_id, occurred_at=now
    )


async def approve_member(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    roles: Iterable[Role],
    now: datetime,
) -> tuple[Role, ...]:
    """Pending to active, with the roles the Admin chose. **This is the human gate.**

    A code admits somebody to the queue and nothing else; this is where a person
    decides. The roles are the approver's rather than the invitation's — the
    invitation's `grants_roles` pre-fills the form and does not bind it, because
    an hour can pass between creating a code and finding out who used it.

    **Only a `pending` membership can be approved.** An active one is already in,
    and a removed one was removed — approving either from here would be a route to
    resurrect a membership without the `member_added` fact that should accompany
    it. Both answer not-found, which is the same answer a user id from another
    workspace gets.
    """
    member = (await db.execute(LOAD_MEMBER, {"user_id": user_id})).one_or_none()
    if member is None or member.status != MemberStatus.PENDING.value:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such pending member",
        )

    await db.execute(SET_MEMBER_STATUS, {"status": MemberStatus.ACTIVE.value, "user_id": user_id})

    assigned = tuple(sorted(set(roles), key=lambda role: role.value))
    for role in assigned:
        await db.execute(
            INSERT_ROLE_BINDING,
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "role": role.value,
                "granted_by": actor_id,
                "granted_at": now,
            },
        )

    await events.member_join_approved(
        db, workspace_id=workspace_id, actor_id=actor_id, user_id=user_id, occurred_at=now
    )
    for role in assigned:
        await events.role_assigned(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            user_id=user_id,
            role=role,
            occurred_at=now,
        )

    await _sync_admin_gauge(db, workspace_id)
    return assigned


async def reject_member(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    now: datetime,
) -> None:
    """Pending to removed. The row stays, and so does the request that produced it.

    A rejected person is indistinguishable from a removed one everywhere
    downstream, which is the point: `may()` already answers correctly for
    `removed`, and inventing a fourth status would be a fourth thing every
    permission query has to know about.

    No `_refuse_if_last_admin` call, and none is possible: a pending member holds
    no role bindings, so rejecting one cannot take the last Admin away.
    """
    member = (await db.execute(LOAD_MEMBER, {"user_id": user_id})).one_or_none()
    if member is None or member.status != MemberStatus.PENDING.value:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such pending member",
        )

    await db.execute(SET_MEMBER_STATUS, {"status": MemberStatus.REMOVED.value, "user_id": user_id})
    await events.member_join_rejected(
        db, workspace_id=workspace_id, actor_id=actor_id, user_id=user_id, occurred_at=now
    )


async def redeem_invite(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    code: str,
    now: datetime,
) -> RedeemedInvite:
    """A code, from the lobby, to a place in a workspace's pending queue.

    **Two transactions, and the split is what the lobby forces.** The caller is in
    no workspace, so the first read cannot run under a tenant at all: it runs under
    `invite_lookup_transaction`, where the `invite_redeem` policy admits exactly
    the row whose `code_hash` matches the digest the caller presented — an
    unfiltered `SELECT *` there returns one row or none. That read answers *which
    workspace*, and its answer is treated as untrusted for everything else: the
    second transaction opens that workspace's ordinary tenant context and re-reads
    the invitation `FOR UPDATE`, so two people spending the last use of a code race
    against a row lock rather than against each other.

    **Every failure is the same refusal** (:func:`_not_redeemable`). A code that
    never existed, one that expired, one that was revoked and one that is exhausted
    are byte-identical, so the response cannot be used to confirm that a string was
    ever an invitation.

    **Re-redeeming is not an error.** Somebody already pending gets their pending
    answer back and no second event; somebody already active is told they are in.
    Neither spends a use.
    """
    digest = hash_code(normalise_code(code))

    async with invite_lookup_transaction(sessionmaker, code_hash=digest) as lookup:
        found = (await lookup.execute(LOAD_INVITE_BY_CODE, {"code_hash": digest})).one_or_none()

    if found is None:
        invite_redeem_total.labels(outcome="refused").inc()
        raise _not_redeemable()

    async with workspace_transaction(sessionmaker, found.workspace_id) as db:
        invite = (
            await db.execute(LOAD_INVITE_FOR_UPDATE, {"invite_id": found.id})
        ).one_or_none()
        name = await db.scalar(LOAD_WORKSPACE_NAME, {"workspace_id": found.workspace_id})
        if invite is None or name is None:
            # The invitation or its workspace is not visible under that
            # workspace's own tenant, which neither row can normally be. It
            # answers as an unusable invitation rather than as an error.
            invite_redeem_total.labels(outcome="refused").inc()
            raise _not_redeemable()

        # **The membership is read before the invitation's liveness is judged**,
        # and the order is what makes re-presenting a code idempotent. A
        # single-use code is exhausted the instant its one redemption lands, so
        # judging liveness first would answer *"not redeemable"* to the very
        # person who just redeemed it — on a page reload, thirty seconds later.
        # Nothing is disclosed by the reordering: the only extra answer it gives
        # is to somebody who is already a member or already in the queue, and that
        # is a fact about themselves.
        member = (await db.execute(LOAD_MEMBER, {"user_id": user_id})).one_or_none()
        if member is not None and member.status == MemberStatus.ACTIVE.value:
            invite_redeem_total.labels(outcome="active").inc()
            return RedeemedInvite(
                workspace_id=invite.workspace_id,
                workspace_name=name,
                status=MemberStatus.ACTIVE,
            )
        if member is not None and member.status == MemberStatus.PENDING.value:
            invite_redeem_total.labels(outcome="pending").inc()
            return RedeemedInvite(
                workspace_id=invite.workspace_id,
                workspace_name=name,
                status=MemberStatus.PENDING,
            )

        if not _invite_is_live(invite, now):
            invite_redeem_total.labels(outcome="refused").inc()
            raise _not_redeemable()

        await db.execute(
            INSERT_PENDING_MEMBER,
            {
                "workspace_id": invite.workspace_id,
                "user_id": user_id,
                "added_by": invite.created_by,
                "added_at": now,
            },
        )
        # A previously removed or rejected person: the row is retained (A-151), so
        # the insert above did nothing and the status has to be lifted. They go
        # back into the queue rather than back into the workspace — the same code
        # that admits a stranger cannot quietly reinstate somebody an Admin
        # removed.
        await db.execute(
            SET_MEMBER_STATUS, {"status": MemberStatus.PENDING.value, "user_id": user_id}
        )
        await db.execute(BUMP_INVITE_USE, {"invite_id": invite.id})
        await events.member_join_requested(
            db,
            workspace_id=invite.workspace_id,
            actor_id=user_id,
            invite_id=invite.id,
            occurred_at=now,
        )

    invite_redeem_total.labels(outcome="pending").inc()
    return RedeemedInvite(
        workspace_id=found.workspace_id, workspace_name=name, status=MemberStatus.PENDING
    )


async def claim_email_invites(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    email: str,
    now: datetime,
) -> tuple[str, ...]:
    """Turn every live seat reserved for this address into an active membership.

    **Called from two places, and the second one is what makes it reliable**:
    :func:`register_account`, so somebody who signs up because a colleague invited
    them lands in the workspace on their first screen; and `api.login`, so an Admin
    can invite a person who *already has an account* and have it arrive on their
    next sign-in. Without the second call the email invitation would only work for
    strangers, and a failed claim during registration would strand a row nothing
    would ever look at again.

    **The two calls sit on opposite sides of the session.** Registration claims
    *before* signing the person in, so a single claimed membership takes them
    straight into the workspace. Sign-in claims *after*, because `sign_in` counts
    memberships to decide that very thing and this module cannot be imported from
    `sessions` — so a claim that lands during sign-in shows up on the chooser
    instead, one click away. The alternative was a cycle between the two modules,
    which is a worse thing to own than a click.

    **Idempotent, and cheap when there is nothing to do.** The lookup is one
    indexed read against a partial index over an address that usually has no rows
    at all; a person already active in the workspace consumes the invitation and
    gets no second `member_added`.

    **No approval, deliberately.** An email invitation names one person and was
    written by an Admin — that is the same decision `add_member` records, so the
    person is `active` with the invitation's roles. The pending queue exists for
    codes, where the workspace does not know who is holding one.

    The `member_added` event names the **inviting Admin** as its actor, not the
    person arriving. The act being recorded is the invitation, which is theirs; the
    arrival is when it took effect.
    """
    folded = email.strip().lower()

    async with invite_lookup_transaction(sessionmaker, email=folded) as lookup:
        rows = (await lookup.execute(LOAD_EMAIL_INVITES, {"invited_email": folded})).all()

    claimed: list[str] = []
    for row in rows:
        if not _invite_is_live(row, now):
            continue

        async with workspace_transaction(sessionmaker, row.workspace_id) as db:
            invite = (
                await db.execute(LOAD_INVITE_FOR_UPDATE, {"invite_id": row.id})
            ).one_or_none()
            if invite is None or not _invite_is_live(invite, now):
                continue

            await db.execute(BUMP_INVITE_USE, {"invite_id": invite.id})

            member = (await db.execute(LOAD_MEMBER, {"user_id": user_id})).one_or_none()
            if member is not None and member.status == MemberStatus.ACTIVE.value:
                # Already in. The invitation is spent above so it stops showing on
                # the Admin's list as an outstanding one, and nothing else happens.
                continue

            await db.execute(
                INSERT_MEMBER,
                {
                    "workspace_id": invite.workspace_id,
                    "user_id": user_id,
                    "added_by": invite.created_by,
                    "added_at": now,
                },
            )
            await db.execute(
                SET_MEMBER_STATUS, {"status": MemberStatus.ACTIVE.value, "user_id": user_id}
            )

            assigned = tuple(Role(value) for value in invite.grants_roles)
            for role in assigned:
                await db.execute(
                    INSERT_ROLE_BINDING,
                    {
                        "workspace_id": invite.workspace_id,
                        "user_id": user_id,
                        "role": role.value,
                        "granted_by": invite.created_by,
                        "granted_at": now,
                    },
                )

            await events.member_added(
                db,
                workspace_id=invite.workspace_id,
                actor_id=invite.created_by,
                user_id=user_id,
                occurred_at=now,
            )
            for role in assigned:
                await events.role_assigned(
                    db,
                    workspace_id=invite.workspace_id,
                    actor_id=invite.created_by,
                    user_id=user_id,
                    role=role,
                    occurred_at=now,
                )

            await _sync_admin_gauge(db, invite.workspace_id)
            claimed.append(invite.workspace_id)

    return tuple(claimed)


async def grant_access(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    grantee_user_id: str,
    level: GrantLevel,
    now: datetime,
) -> GrantLevel:
    """Grant or raise a per-prompt grant, and record it (A-112, AC-12).

    An upsert, because raising a viewer to an editor is the same act as granting
    an editor to somebody who had nothing, and a route that refused the first
    would make the SPA revoke-then-grant — two events for one intent, with a
    window in between where the person could see nothing.

    **`prompt_id` is not validated against anything**, and cannot be: this module
    may not read `prompt_property` (ADR-0020), and the foreign key that would
    check it would point at prompt-registry's table in the forbidden direction.
    The caller has already read the prompt to check `prompt.grant`, which is
    where the existence question is answered.
    """
    if grantee_user_id == actor_id:
        # Not a security rule — a usability one. Granting yourself access to a
        # prompt you can already grant on is a no-op the SPA should not be able
        # to write into the trail.
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.VALIDATION_FAILED,
            message="an actor cannot grant access to themselves",
        )

    member = (await db.execute(LOAD_MEMBER, {"user_id": grantee_user_id})).one_or_none()
    if member is None or member.status != MemberStatus.ACTIVE.value:
        # Not-found rather than a validation error: the grantee is a subject the
        # caller may not be able to see, and A-116's rule applies to people the
        # same way it applies to prompts.
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such member",
        )

    await db.execute(
        UPSERT_GRANT,
        {
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "grantee_user_id": grantee_user_id,
            "level": level.value,
            "granted_by": actor_id,
            "granted_at": now,
        },
    )
    await events.access_granted(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        grantee_user_id=grantee_user_id,
        level=level,
        occurred_at=now,
    )
    grant_total.labels(level=level.value, operation="grant").inc()
    return level


async def revoke_access(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    grantee_user_id: str,
    now: datetime,
) -> GrantLevel:
    """Withdraw a grant. Effective on the next request, with no TTL (A-114, AC-6).

    The level is **read before the delete** and carried into the event. It is the
    only place that fact survives: the row is gone afterwards, and nothing else
    in the system records what a revoked grant used to confer.
    """
    row = (
        await db.execute(
            LOAD_GRANT, {"prompt_id": prompt_id, "grantee_user_id": grantee_user_id}
        )
    ).one_or_none()
    if row is None:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such grant",
        )

    level = GrantLevel(row.level)
    await db.execute(DELETE_GRANT, {"prompt_id": prompt_id, "grantee_user_id": grantee_user_id})
    await events.access_revoked(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        grantee_user_id=grantee_user_id,
        level=level,
        occurred_at=now,
    )
    grant_total.labels(level=level.value, operation="revoke").inc()
    return level


async def create_api_key(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    name: str,
    scope_model_names: Iterable[str],
    now: datetime,
) -> MintedKey:
    """Issue a consumer key. **The plaintext is in the return value and nowhere else.**

    AC-7: it appears in the creation response and in no other response, log line,
    metric label or history event, and the stored row cannot reconstruct it. The
    event this writes has an **empty registered detail allow-list** (revision
    0005), so there is no slot the secret or its scope could be put into even by
    somebody trying.

    Scope is explicit and default-deny (A-081). An empty list is a legal key that
    resolves nothing — useful for provisioning a consumer before deciding what it
    may reach, and the failure mode is a not-found the consumer cannot
    distinguish from an unknown model, which is the point.
    """
    minted = mint_key()
    await db.execute(
        INSERT_API_KEY,
        {
            "id": minted.key_id,
            "workspace_id": workspace_id,
            "name": name,
            "key_hash": minted.key_hash,
            "last_four": minted.last_four,
            "scope_model_names": list(scope_model_names),
            "created_by": actor_id,
            "created_at": now,
        },
    )
    await events.api_key_created(
        db, workspace_id=workspace_id, actor_id=actor_id, key_id=minted.key_id, occurred_at=now
    )
    return minted


async def revoke_api_key(
    db: AsyncSession, *, workspace_id: str, actor_id: str, key_id: str, now: datetime
) -> None:
    """Stamp `revoked_at`. The very next request presenting the key is refused.

    An `UPDATE` and not a `DELETE`, and revision 0006 withholds the privilege to
    do otherwise: a deleted row would orphan the `api_key_revoked` event, whose
    `target_id` names a key nobody could then look up, in a table nothing can
    remove the event from.

    Idempotent by predicate — `WHERE revoked_at IS NULL` — so a second revoke
    answers not-found rather than moving the timestamp. Moving it would rewrite
    when access ended, which is the one fact somebody reads this row for.
    """
    result = await db.execute(REVOKE_API_KEY, {"key_id": key_id, "now": now})
    if result.rowcount == 0:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such key",
        )

    await events.api_key_revoked(
        db, workspace_id=workspace_id, actor_id=actor_id, key_id=key_id, occurred_at=now
    )
    key_revoked_total.inc()


async def set_api_key_scope(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    key_id: str,
    scope_model_names: Iterable[str],
    now: datetime,
) -> list[str]:
    """Replace a live key's scope. **Wholesale, never a delta.**

    A PUT that takes the whole list, for the reason
    ``dataset_attachment.replace`` takes the whole tick-state: an add/remove pair
    makes the caller's view of the current scope part of the protocol, and two
    administrators widening a key at the same time would each apply a delta to a
    list they read before the other's write. Replacement makes the last writer's
    intent the whole of the outcome, which is the only outcome anybody can reason
    about afterwards.

    **Order is preserved and duplicates are not removed here.** ``= ANY(...)`` in
    ``KEY_RESOLVES_MODEL`` is set membership, so neither affects what the key can
    reach; normalising would mean this function deciding that two spellings of a
    caller's intent are the same, and the one place that decision belongs is the
    schema's own uniqueness, which this column does not have.

    **No plaintext, no hash, no ``last_four`` is read or written.** This function
    changes what a credential may reach and never touches the credential.
    """
    stored = (
        await db.execute(
            SET_API_KEY_SCOPE,
            {"key_id": key_id, "scope_model_names": list(scope_model_names)},
        )
    ).scalar_one_or_none()

    if stored is None:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such key",
        )

    await events.api_key_scope_set(
        db, workspace_id=workspace_id, actor_id=actor_id, key_id=key_id, occurred_at=now
    )
    return list(stored)


async def change_own_password(
    db: AsyncSession, *, user_id: str, current_password: str, new_password: str
) -> None:
    """Change your own password, and clear A-110's forced-change flag.

    **The current password is verified even though the caller holds a session.**
    A session is a cookie somebody could have taken from an unlocked machine, and
    a password change is the one operation that would lock the real owner out —
    so this is the single route where re-proving the credential is worth a
    second argon2id verification.

    **No history event.** Property history is the log of state changes to things
    the product is *about* (A-044); a password is a credential, and recording its
    rotation would put an authentication fact into the audit trail for the same
    reason a sign-in is kept out of it.
    """
    row = (await db.execute(LOAD_PASSWORD_HASH, {"user_id": user_id})).one_or_none()
    if row is None:
        raise ManagementRefusal(
            status_code=403,
            code=ErrorCode.USER_IS_TOMBSTONED,
            message="this account can no longer be used",
        )

    if not passwords.verify(row.password_hash, current_password):
        raise ManagementRefusal(
            status_code=401,
            code=ErrorCode.AUTHENTICATION_FAILED,
            message="the current password is not correct",
        )

    await db.execute(
        SET_PASSWORD,
        {"password_hash": passwords.hash_password(new_password), "user_id": user_id},
    )


async def tombstone_user(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    actor_id: str,
    user_id: str,
    now: datetime,
) -> tuple[str, ...]:
    """ADR-0054 / A-151, in full. **Irreversible, and the only erasure in Prope.**

    Returns the workspaces an event was written into, so a caller can assert the
    count rather than trust it.

    **It opens its own transaction and it spans every workspace**, which is why
    it takes a sessionmaker where every other command here takes a session. The
    person's memberships, role bindings, grants and sessions live in five
    tenant-scoped tables, and a request holding one tenant can reach none of the
    others — so the workspaces are enumerated through `access.list_workspaces()`,
    ADR-0051's sanctioned identifier-only bypass, and every read and write after
    that runs under ordinary policy inside that workspace's own context.

    **One transaction across all of them**, with the tenant re-set inside it
    rather than one transaction per workspace. See the comment at the loop: a
    tombstone that cleared the identity columns and then failed halfway through
    the workspaces would leave a person with no name, live grants, and no
    `user_tombstoned` event to explain either.

    **The pre-condition is a refusal, not a cleanup.** A person must already hold
    no active membership: each removal writes its own `member_removed` event in
    its own workspace, and the tombstone is the account-level act that follows.
    Collapsing the two would put "left this workspace" and "erased from Prope"
    into one ambiguous event.

    What it does **not** touch, and each absence is a decision:

    * **`history_event`** — no row deleted, no `actor_id` nulled, blanked,
      re-pointed or anonymised. Ever. `prope_app` could not do it if it tried
      (ADR-0025). This is the whole of ADR-0054.
    * **Consumer API keys** — a key belongs to the workspace, not to the person
      who created it (A-113). Revoking a departing person's keys on an HR event
      would break a consuming product's traffic silently.
    * **`workspace_member` rows** — retained, moved to `removed`. They are how
      this operation knows which workspaces to write into.
    * **`last_login_at`** — a timestamp is not identifying, and zeroing it would
      destroy the only signal that an account was ever used.
    """
    async with sessionmaker() as db:
        async with db.begin():
            # ONE transaction, many tenants. `workspace_transaction` opens its
            # own and would give this operation one per workspace, so the tenant
            # is re-set inside the single transaction instead — `set_config(...,
            # true)` is transaction-local and may be issued again, and each call
            # governs the statements that follow it.
            #
            # This is the only place in Prope that does that, and it is not a
            # loophole: the statement is `prope.db.session.SET_TENANT` imported
            # rather than re-spelled, the value is still a bound parameter, and
            # every read and write below still runs under the ordinary policy for
            # whichever workspace is current. What is escaped is the
            # one-workspace-per-transaction convention (ADR-0040), and A-151
            # requires exactly that: a tombstone that cleared the identity
            # columns and then failed halfway through the workspaces would leave
            # a person with no name, live grants, and no event explaining either.
            workspace_ids = (await db.execute(LIST_WORKSPACES)).scalars().all()

            touched: list[str] = []
            for workspace_id in workspace_ids:
                await db.execute(SET_TENANT, {"ws": workspace_id})
                membership = (
                    await db.execute(LOAD_ANY_MEMBERSHIP, {"user_id": user_id})
                ).one_or_none()
                if membership is None:
                    continue
                if membership.status == MemberStatus.ACTIVE.value:
                    raise ManagementRefusal(
                        status_code=409,
                        code=ErrorCode.USER_STILL_HAS_MEMBERSHIP,
                        message="remove this person from every workspace before tombstoning them",
                        details={"workspace_id": workspace_id},
                    )
                touched.append(workspace_id)

            # `WHERE status = 'active'` is what makes a second tombstone a no-op
            # rather than a second set of events, so this statement is the one
            # that decides and it runs before any per-workspace write.
            cleared = await db.execute(
                TOMBSTONE_USER, {"user_id": user_id, "actor_id": actor_id, "now": now}
            )
            if cleared.rowcount == 0:
                raise ManagementRefusal(
                    status_code=404,
                    code=ErrorCode.NOT_FOUND,
                    message="no such user",
                )

            for workspace_id in touched:
                await db.execute(SET_TENANT, {"ws": workspace_id})
                await delete_user_sessions(db, user_id)
                await db.execute(DELETE_ALL_ROLE_BINDINGS, {"user_id": user_id})
                await db.execute(DELETE_GRANTS_FOR_USER, {"grantee_user_id": user_id})
                await events.user_tombstoned(
                    db,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    user_id=user_id,
                    occurred_at=now,
                )
                await _sync_admin_gauge(db, workspace_id)

    return tuple(touched)

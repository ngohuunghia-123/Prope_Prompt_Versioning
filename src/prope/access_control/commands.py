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
from prope.access_control.keys import MintedKey, mint_key
from prope.access_control.observability import (
    admin_count,
    grant_total,
    key_revoked_total,
    last_admin_refused_total,
)
from prope.access_control.sessions import delete_user_sessions
from prope.db.session import SET_TENANT, workspace_transaction
from prope.errors import ErrorCode
from prope.session_auth import ManagementRefusal

__all__ = [
    "USER_ID_PREFIX",
    "WORKSPACE_ID_PREFIX",
    "add_member",
    "change_own_password",
    "create_api_key",
    "create_workspace",
    "grant_access",
    "remove_member",
    "revoke_access",
    "revoke_api_key",
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

INSERT_ROLE_BINDING = text(
    """
    INSERT INTO access.role_binding (workspace_id, user_id, role, granted_by, granted_at)
    VALUES (:workspace_id, :user_id, :role, :granted_by, :granted_at)
    ON CONFLICT (workspace_id, user_id, role) DO NOTHING
    """
)

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
    """The workspace, its creator's membership, their Admin binding, and the event.

    **Four writes, one transaction, and the order is a dependency order rather
    than a preference.** A-109 makes the workspace the tenancy root and A-117
    makes an Adminless workspace unreachable, so a partial commit here produces
    exactly the frozen state the rest of this file exists to prevent.

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
        await db.execute(
            INSERT_ROLE_BINDING,
            {
                "workspace_id": workspace_id,
                "user_id": actor_id,
                "role": Role.ADMIN.value,
                "granted_by": actor_id,
                "granted_at": now,
            },
        )
        await events.workspace_created(
            db, workspace_id=workspace_id, actor_id=actor_id, occurred_at=now
        )
        await _sync_admin_gauge(db, workspace_id)

    return CreatedWorkspace(workspace_id=workspace_id, name=name, slug=slug, created_at=now)


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

"""The ten history events this module writes, one builder each (INT-006, A-014).

**Every one of them is appended on the caller's session inside the caller's open
transaction** (ADR-0023). Nothing here opens a transaction, nothing commits, and
nothing catches: `append()` raising fails the caller's transaction, and *that is
the mechanism* behind *"there is no grant without a trail"* (AC-12). A `try` in
this file would be the audit hole the whole design exists to close.

**The action names, target types and detail keys are the registry's, not
this module's.** Revision 0005 seeded all ten and revision 0006 amended three of
their payloads; `append()` validates every draft against the registered
allow-list and refuses an unregistered key with `unknown_detail_key`. So the
constants below are a **mirror**, and the mirror is checked — a drift shows up as
a refused append in a test, not as a silently dropped field.

**Sign-ins are not events, and neither are sign-outs.** Property history is the
log of *state changes* (A-044); authentication traffic is metrics and logs.
Putting a login here would turn the audit trail into an access log, which is the
same argument that keeps a gateway call out of it (A-039).

**`user_tombstoned` carries no reason and no details, and that is the one place
this file departs from house style.** `requires_reason` is how the pack normally
makes a rare, irreversible action accountable — and here it would be the exact
mechanism by which an erased name walks back into the one table nothing can be
removed from. *"John Smith left the company"* is a free-text reason nobody would
flag in review. The accountability comes from `tombstoned_by`, which is an id
(ADR-0054 §7).
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.domain import GrantLevel, Role
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft

__all__ = [
    "access_granted",
    "access_revoked",
    "api_key_created",
    "api_key_revoked",
    "member_added",
    "member_removed",
    "role_assigned",
    "role_revoked",
    "user_tombstoned",
    "workspace_created",
]


async def _append(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    occurred_at: datetime,
    details: dict[str, object] | None = None,
) -> str:
    """One construction site for all ten drafts.

    **`scope_prompt_id` is never set, on any of them.** All six of this module's
    target types — `workspace`, `member`, `role`, `prompt_grant`, `api_key`,
    `user` — are in property-history's `NEVER_PROMPT_SCOPED_TARGET_TYPES`, so a
    NULL scope here is expected rather than the silent gap
    `null_scope_prompt_total` counts. `access_granted` is the one that looks like
    it should carry a prompt scope and deliberately does not: a grant is a fact
    about *who may see a prompt*, and putting it in that prompt's Activity feed
    would show every viewer the list of everybody else who was let in.

    **`actor_type` is always `USER`.** Nothing in this module acts on its own —
    there is no scheduled job and no background sweep (the lock file's
    `deployment_target`), so every event here has a person behind it.
    """
    return await append(
        db,
        HistoryEventDraft(
            workspace_id=workspace_id,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            occurred_at=occurred_at,
            details=details or {},
        ),
    )


async def workspace_created(
    db: AsyncSession, *, workspace_id: str, actor_id: str, occurred_at: datetime
) -> str:
    """The first event in a workspace's life, and the first row under its tenant.

    Written in the same transaction as the workspace row **and** its creator's
    Admin binding (A-109, A-117), so a workspace that exists is a workspace with
    an Admin and a trail. There is no ordering in which two of the three survive.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="workspace_created",
        target_type="workspace",
        target_id=workspace_id,
        occurred_at=occurred_at,
    )


async def member_added(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    occurred_at: datetime,
) -> str:
    """An Admin created an account and added it here (A-110). No invitation exists.

    `target_id` is the person added, not the membership row — the row has a
    composite key and no id, and *"who was added"* is the question a reader of the
    trail is asking.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="member_added",
        target_type="member",
        target_id=user_id,
        occurred_at=occurred_at,
    )


async def member_removed(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    occurred_at: datetime,
) -> str:
    """A membership moved to `removed`. The row is retained (A-151).

    This is the trail of departure, and it is **per workspace**. A tombstone is
    the account-level act that follows every one of them, which is why A-151
    refuses a tombstone while any membership is still active: two facts, recorded
    separately, rather than one ambiguous event.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="member_removed",
        target_type="member",
        target_id=user_id,
        occurred_at=occurred_at,
    )


async def role_assigned(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    role: Role,
    occurred_at: datetime,
) -> str:
    """One role bound to one person. Registered keys: `{role, grantee_user_id}`.

    `target_id` is the role name rather than the person, because `target_type` is
    `role` — the pairing is fixed by `fk_history_event_action` and a mismatch
    poisons the transaction rather than being refused by name. The person is in
    `details.grantee_user_id`, which is why that key was registered.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="role_assigned",
        target_type="role",
        target_id=role.value,
        occurred_at=occurred_at,
        details={"role": role.value, "grantee_user_id": user_id},
    )


async def role_revoked(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    role: Role,
    occurred_at: datetime,
) -> str:
    """The mirror of :func:`role_assigned`, and it carries the same keys.

    It did not, until revision 0006. Revision 0005 seeded this action with an
    **empty** `detail_keys` while its counterpart already carried
    `{role, grantee_user_id}` — so the trail recorded that a role was taken away
    and not which one, from whom. An asymmetric pair is worse than either
    symmetric one, because a reader believes the two are comparable. D-62.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="role_revoked",
        target_type="role",
        target_id=role.value,
        occurred_at=occurred_at,
        details={"role": role.value, "grantee_user_id": user_id},
    )


async def access_granted(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    grantee_user_id: str,
    level: GrantLevel,
    occurred_at: datetime,
) -> str:
    """Somebody was let into a private prompt. Keys: `{grantee_user_id, level}`.

    AC-12 requires the event to carry *"actor, grantee, level, and timestamp"*.
    Three of those are envelope columns; `grantee_user_id` and `level` had nowhere
    to go until revision 0006 registered them (D-62), because revision 0005
    derived the payload from a lock-file `outputs` block that lists event names
    and says nothing about detail keys.

    Reading them off the `prompt_grant` row instead was the alternative and it
    does not work: :func:`access_revoked` **deletes** that row, so a revocation
    event would point at nothing.

    This module owns `prompt_grant`, which is why the event is written here and
    not in prompt-registry — the map listed it there and it was corrected while
    this module was locked. The registry's own event is `access_level_changed`,
    a different fact about a field it does own.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="access_granted",
        target_type="prompt_grant",
        target_id=prompt_id,
        occurred_at=occurred_at,
        details={"grantee_user_id": grantee_user_id, "level": level.value},
    )


async def access_revoked(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    grantee_user_id: str,
    level: GrantLevel,
    occurred_at: datetime,
) -> str:
    """A grant was withdrawn. Effective on the next request, with no TTL (A-114).

    `level` is the level the grant **had**, read before the delete. Recording it
    is what makes the two counters subtract: without it, *"how many editor grants
    are live"* is unanswerable from the trail the moment anything is revoked.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="access_revoked",
        target_type="prompt_grant",
        target_id=prompt_id,
        occurred_at=occurred_at,
        details={"grantee_user_id": grantee_user_id, "level": level.value},
    )


async def api_key_created(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    key_id: str,
    occurred_at: datetime,
) -> str:
    """A consumer key was issued. **No detail keys, and that is a security property.**

    The registry allows none for this action, so there is no registered place to
    put the scope, the name, the `last_four`, or — the one that matters — any
    part of the secret. AC-7 asserts the plaintext appears in exactly one response
    and *"in no other response, log line, metric label, or history event"*, and an
    empty allow-list is what makes the last of those four true by construction
    rather than by review.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="api_key_created",
        target_type="api_key",
        target_id=key_id,
        occurred_at=occurred_at,
    )


async def api_key_revoked(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    key_id: str,
    occurred_at: datetime,
) -> str:
    """A consumer key was revoked. The next request presenting it is refused.

    The key row survives with a `revoked_at`; revision 0006 withholds `DELETE` on
    the table. A deleted key row would orphan this very event — `target_id` would
    name a key nobody could look up, in a table nothing can remove the event from.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="api_key_revoked",
        target_type="api_key",
        target_id=key_id,
        occurred_at=occurred_at,
    )


async def user_tombstoned(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    user_id: str,
    occurred_at: datetime,
) -> str:
    """One per workspace the person had been a member of. Empty details, no reason.

    **The emptiness is the decision** (ADR-0054 §7, A-151). Every candidate detail
    key here — a name, an email, a reason — is a fact about the person being
    erased, written into the one table from which nothing can ever be removed.
    `requires_reason` is `false` for this action alone among the consequential
    ones, and `detail_keys` is empty, so there is no registered slot a later
    contributor could fill "just for context".

    Written once **per workspace**, including ones the person was only ever
    removed from, so that a reader of any workspace's trail can tell why an
    `actor_id` in it no longer resolves. `workspace_member` rows are retained
    precisely so those workspaces are known without scanning history.
    """
    return await _append(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        action="user_tombstoned",
        target_type="user",
        target_id=user_id,
        occurred_at=occurred_at,
    )

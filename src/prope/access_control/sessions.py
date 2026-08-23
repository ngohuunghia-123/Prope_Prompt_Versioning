"""Issuing, refreshing and ending a session row, and the sign-in path itself.

**The three security properties of `POST /api/v1/auth/login` live in this file
and are the reason it exists apart from `api.py`.**

1. **The limiter runs before the user row is read and before any hash is
   computed** (ADR-0043). That ordering is what bounds argon2id's aggregate cost
   on a 4-vCPU host, and it is also what makes a rate-limited attempt
   timing-identical to a wrong password — neither reaches the hasher.
2. **The hash comparison runs even when there is nothing to compare against.**
   `passwords.verify(None, ...)` burns the same work, so an unknown email, a
   wrong password and a **tombstoned** account cost the same wall time (A-144,
   A-151).
3. **All three failures return the same value**, so `api.py` has one refusal to
   render and cannot accidentally grow a second. :func:`sign_in` returns
   `SignInResult`, whose failure form carries nothing a caller could branch on
   except for the metric it should increment.

**The session id is not a ULID, and that is the one place this module departs
from A-045's identifier convention.** Every other id in Prope names a row
somebody is allowed to name; this one *is* a bearer credential (ADR-0029), so it
is 256 bits from a CSPRNG behind a `ses_` prefix. A ULID would put a millisecond
timestamp and a monotonic counter into a token whose only defence is that it
cannot be guessed — and the prefix convention would have quietly supplied the
reason to do it. Revision 0006's `ck_session_id_prefix` keeps the prefix; the
entropy is this file's.
"""

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control import passwords
from prope.access_control.domain import MemberStatus, Role
from prope.access_control.limiter import LoginLimiter
from prope.access_control.limiter import limiter as process_limiter
from prope.access_control.observability import login_duration_seconds, login_total
from prope.db.session import lobby_transaction, workspace_transaction
from prope.session_auth import ActorSession

__all__ = [
    "PUBLIC_SESSION_ID_PREFIX",
    "SESSION_ID_PREFIX",
    "SESSION_LIFETIME",
    "Membership",
    "SignInResult",
    "delete_lobby_sessions",
    "delete_session",
    "delete_user_sessions",
    "enter_workspace",
    "issue_session",
    "list_memberships",
    "public_session_id",
    "sign_in",
]

#: ADR-0003's typed prefix, kept even though the value is a credential rather
#: than an identifier — a log line that ever *did* leak one would at least be
#: greppable, and `ck_session_id_prefix` refuses anything else.
SESSION_ID_PREFIX = "ses_"

#: 256 bits, the same budget as an API key secret and for the same reason: this
#: is the whole of a person's authority and its only defence is that it cannot be
#: guessed.
SESSION_SECRET_BYTES = 32

#: Twelve hours. Long enough for a working day without a re-sign-in in the middle
#: of a review, short enough that a cookie left on a shared machine expires the
#: same day. It is a **ceiling and not a heartbeat**: sign-out, member removal and
#: the tombstone all delete the row and take effect on the next request
#: (ADR-0022), so expiry is what happens to sessions nobody ends rather than the
#: mechanism by which sessions end.
SESSION_LIFETIME = timedelta(hours=12)

ISSUE_SESSION = text(
    """
    INSERT INTO access.session (
        id, user_id, workspace_id, created_at, expires_at, last_seen_at, user_agent_hash
    ) VALUES (
        :id, :user_id, :workspace_id, :created_at, :expires_at, :created_at, :user_agent_hash
    )
    """
)

#: By primary key AND under the tenant policy. The policy is what makes a stolen
#: id from another workspace a no-op rather than a cross-tenant sign-out.
DELETE_SESSION = text("DELETE FROM access.session WHERE id = :id")

#: A-151: the tombstone ends every session the person holds. Also the shape a
#: future "sign out everywhere" would use, which is why it is a function rather
#: than a line inside the tombstone.
DELETE_USER_SESSIONS = text("DELETE FROM access.session WHERE user_id = :user_id")

#: Reads `access."user"` — a global table with no policy — by its unique email.
#: `status` is NOT filtered here: a tombstoned row has a NULL `password_hash`,
#: and letting it through to :func:`~prope.access_control.passwords.verify` is
#: what keeps a tombstoned email indistinguishable from an unknown one (A-151).
#: Filtering on `status = 'active'` would have skipped the hash and reopened the
#: enumeration oracle at exactly the point ADR-0054 closed it.
LOAD_USER_BY_EMAIL = text(
    """
    SELECT id, password_hash, must_change_password
    FROM   access."user"
    WHERE  email = :email
    """
)

#: ADR-0051's generic enumerator. Identifiers only — every read that follows runs
#: under ordinary policy, which is the property that distinguishes a sanctioned
#: bypass from a hole.
LIST_WORKSPACES = text("SELECT access.list_workspaces()")

#: Run once per workspace id the enumerator returned, each inside that
#: workspace's own tenant context, so the policy is doing its job on every read.
LOAD_ACTIVE_MEMBERSHIP = text(
    """
    SELECT added_at
    FROM   access.workspace_member
    WHERE  user_id = :user_id AND status = 'active'
    """
)

#: The same read, widened for the workspace chooser (ADR-0056). It is the one
#: query behind both `GET /api/v1/auth/workspaces` and the sign-in decision, so
#: the list a person is shown and the list sign-in counts cannot disagree.
#:
#: **`removed` is excluded and `pending` is not.** A workspace somebody was
#: removed from is not theirs to see; a workspace they have *asked* to join is,
#: because the alternative is a screen that says nothing happened when a request
#: is sitting in somebody's queue. That disclosure is bounded to a person who
#: already held a valid code for that workspace.
#:
#: The `LEFT JOIN` and the `FILTER` are `LIST_MEMBERS`': a member with no role
#: binding is a legitimate state — every pending member is one — and an inner
#: join would drop exactly the rows this read exists to show.
LOAD_MEMBERSHIP = text(
    """
    SELECT w.id   AS workspace_id,
           w.name,
           w.slug,
           wm.added_at,
           wm.status,
           coalesce(
               array_agg(rb.role ORDER BY rb.role) FILTER (WHERE rb.role IS NOT NULL),
               '{}'
           ) AS roles
    FROM   access.workspace_member AS wm
    JOIN   access.workspace        AS w  ON w.id = wm.workspace_id
    LEFT   JOIN access.role_binding AS rb
      ON   rb.workspace_id = wm.workspace_id AND rb.user_id = wm.user_id
    WHERE  wm.user_id = :user_id
      AND  wm.status IN ('active', 'pending')
    GROUP  BY w.id, w.name, w.slug, wm.added_at, wm.status
    """
)

RECORD_LOGIN = text("UPDATE access.\"user\" SET last_login_at = :now WHERE id = :user_id")

REHASH_PASSWORD = text(
    'UPDATE access."user" SET password_hash = :password_hash WHERE id = :user_id'
)


@dataclass(frozen=True, slots=True)
class SignInResult:
    """Either a session or nothing, plus the label the metric should carry.

    **`session is None` is the whole of what a caller may branch on.** The three
    failures — unknown email, wrong password, rate-limited — differ only in
    `metric_result`, which never leaves the process. That is A-144 expressed as a
    type: a result object with a `reason` field would be a field somebody
    eventually renders, and the response has to be byte-identical for all three.
    """

    session: ActorSession | None
    #: `ok`, `unknown`, `bad_password`, or `rate_limited`. Only the first three
    #: reach `login_total`; a rate-limited attempt never got as far as the hash
    #: and is counted on `login_rate_limited_total` by the limiter itself.
    metric_result: str
    must_change_password: bool = False
    #: Present only on success. The value that goes into the cookie, and the one
    #: string in this module that must never be logged.
    session_id: str | None = None


#: The prefix on the value :func:`public_session_id` returns. **Deliberately not**
#: `SESSION_ID_PREFIX`: the two strings must not be mistakable for one another in
#: a log line, a bug report or a support conversation, because one of them is a
#: credential and the other is safe to paste anywhere.
PUBLIC_SESSION_ID_PREFIX = "sid_"

#: Sixteen hex characters — 64 bits of the digest. Enough that two live sessions
#: colliding is not a thing that happens, short enough to be obviously not a
#: 256-bit token. The truncation is not the security property; the hash is.
PUBLIC_SESSION_ID_LENGTH = 16


def _mint_session_id() -> str:
    return f"{SESSION_ID_PREFIX}{secrets.token_urlsafe(SESSION_SECRET_BYTES)}"


def public_session_id(session_id: str) -> str:
    """A stable, non-reversible name for a session, safe to put in a response body.

    `access.session.id` **is** the bearer credential (ADR-0029), so it may leave
    the process in exactly one place — the `HttpOnly` cookie — and a body field
    carrying it would put it where `localStorage` can hold it and a crash reporter
    can ship it. But the SPA has a real need for *an* identity: it holds a session
    object across a re-authentication and has to answer "is this the same session
    I had a moment ago" without asking the user.

    A digest answers that question and answers no other. It is stable for the life
    of the row, so the SPA can compare two of them; it is one-way, so somebody who
    intercepts a response body cannot authenticate with what they read; and it is
    truncated, so it does not look like something to try.

    **Unsalted, and that is not an oversight.** A salt would have to be stored or
    derived to keep the value stable, and the input is already 256 bits from a
    CSPRNG — there is no dictionary to attack and nothing a rainbow table could
    precompute. Salting would add a key to manage in exchange for nothing.
    """
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return f"{PUBLIC_SESSION_ID_PREFIX}{digest[:PUBLIC_SESSION_ID_LENGTH]}"


def _hash_user_agent(user_agent: str | None) -> str | None:
    """A digest, never the string.

    A user agent is fingerprinting material and is not needed in readable form
    for anything Prope does — the column exists so a future "your other sessions"
    screen can tell two browsers apart, which a digest does perfectly well. A-046
    keeps it out of everything downstream by never storing it in the first place.
    """
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()


async def sign_in(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    password: str,
    source_address: str,
    user_agent: str | None = None,
    now: datetime | None = None,
    limiter: LoginLimiter | None = None,
) -> SignInResult:
    """Authenticate a person and issue a session row. **One failure shape, always.**

    The order of the four steps below is the security property, not an
    implementation detail, and a reordering that looked like a tidy-up would undo
    it:

    1. **Limiter.** Before the read and before the hash (ADR-0043). A rejection
       returns immediately with `rate_limited` and has cost one dictionary
       lookup — which is what makes it timing-indistinguishable from the other
       two failures, since none of them reaches argon2id either... except that
       the other two *do*. So:
    2. **Read the user row, then verify unconditionally.** `verify(None, ...)`
       exists so that step 3 costs the same whether or not step 2 found
       anything.

       The remaining timing difference is the one this design accepts and states:
       a rate-limited attempt skips argon2id entirely and is therefore *faster*
       than a wrong password. It is not an oracle about **accounts** — the
       limiter's state is a fact about the *attacker's own* recent attempts,
       which they already know — and closing it would mean spending 46 MiB and
       70 ms per rejected attempt, which is the exact resource the limiter exists
       to protect.
    3. **Count the workspaces** (ADR-0056). Exactly one active membership binds
       the session to it; none or several issue a **lobby** session that names no
       workspace, and the SPA sends the person to the chooser. This step no longer
       refuses: a person with no membership used to get the same `401` as a
       stranger, which was the only available answer while a session had to name a
       tenant, and is now the wrong one — it would lock somebody out of the screen
       that exists to give them a workspace thirty seconds after they registered.
    4. **Issue the row, clear the email window, stamp `last_login_at`, rehash if
       the cost has moved.**

    `now` and `limiter` are injected for the same reason `prope.worker` injects a
    clock: every downstream value is arithmetic on one instant, and a test of the
    window edge that had to sleep for fifteen minutes is a test nobody runs.
    """
    started = time.perf_counter()
    moment = now or datetime.now(UTC)
    active_limiter = limiter or process_limiter

    def _finish(result: SignInResult) -> SignInResult:
        """One exit, so no branch can forget to observe the duration.

        The histogram matters most on the branches that *fail*: the failure mode
        the lock file predicts is somebody lowering argon2id's cost, and it shows
        up as this series falling well below its target on every branch at once.
        """
        login_duration_seconds.observe(time.perf_counter() - started)
        return result

    refused = active_limiter.check(email=email, source_address=source_address, now=None)
    if refused is not None:
        # Counted by the limiter on login_rate_limited_total{bucket=...}, and
        # deliberately NOT on login_total — see that counter's comment. The
        # bucket that refused is discarded here rather than returned, because a
        # caller holding it is a caller that could render it.
        return _finish(SignInResult(session=None, metric_result="rate_limited"))

    # THE READS RUN WITH NO TENANT AND THE WRITES RUN WITH ONE, and the split is
    # forced rather than stylistic. `access."user"` is global (ADR-0045) and
    # readable without a tenant, which is the only reason a sign-in can find an
    # account at all before it knows which workspace it is in. But
    # `access.workspace_member` and `access.session` are both policied, so the
    # membership read below returns zero rows outside a tenant — which is why the
    # workspace is discovered through the same `SECURITY DEFINER` enumerator the
    # tombstone uses, and not by reading the member table blind.
    async with sessionmaker() as db:
        user = (await db.execute(LOAD_USER_BY_EMAIL, {"email": email})).one_or_none()

    # UNCONDITIONAL. `user is None` and a tombstoned row both reach this with a
    # NULL hash, and both pay for a full argon2id verification.
    stored_hash = user.password_hash if user is not None else None
    if not passwords.verify(stored_hash, password):
        active_limiter.record_failure(email=email, source_address=source_address)
        result = "unknown" if user is None else "bad_password"
        login_total.labels(result=result).inc()
        return _finish(SignInResult(session=None, metric_result=result))

    memberships = await list_memberships(sessionmaker, user.id)
    active = [entry for entry in memberships if entry.status == MemberStatus.ACTIVE]

    # ADR-0056 answers OQ-137, and the rule is: bind only when there is nothing
    # to choose. Exactly one active membership and the session lands in it, so
    # the overwhelmingly common case pays no click. None or several, and the
    # session names no workspace — the person is in the lobby, where they pick,
    # create, or join.
    #
    # **Zero memberships is no longer a refusal.** It used to be counted as
    # `unknown` and rendered as the same `401` a stranger gets, which was correct
    # while a session had to name a tenant: an account that could not resolve one
    # could not hold a session at all. Now it can, and refusing would mean a
    # person who registered thirty seconds ago cannot sign in to the screen that
    # exists to give them a workspace.
    workspace_id = active[0].workspace_id if len(active) == 1 else None

    session_id = await issue_session(
        sessionmaker,
        user_id=user.id,
        workspace_id=workspace_id,
        now=moment,
        user_agent=user_agent,
        # ADR-0043: on every successful login, so raising the cost later migrates
        # hashes as people sign in rather than as a migration. Passed into the
        # session-issuing transaction because a rehash that committed while the
        # session insert rolled back would have changed a password hash for a
        # login that did not happen.
        rehash_to=(
            passwords.hash_password(password)
            if stored_hash is not None and passwords.needs_rehash(stored_hash)
            else None
        ),
        record_login=True,
    )

    # A-144: a successful sign-in clears the EMAIL bucket. The source-address
    # bucket is deliberately left alone — see `LoginLimiter.clear_email`.
    active_limiter.clear_email(email)
    login_total.labels(result="ok").inc()
    return _finish(
        SignInResult(
            session=ActorSession(user_id=user.id, workspace_id=workspace_id),
            metric_result="ok",
            must_change_password=user.must_change_password,
            session_id=session_id,
        )
    )


async def issue_session(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    workspace_id: str | None,
    now: datetime,
    user_agent: str | None = None,
    rehash_to: str | None = None,
    record_login: bool = False,
) -> str:
    """Mint one session row — in a workspace, or in the lobby — and return its id.

    **One function for both, because the two differ in exactly one thing and it is
    not the row.** A tenant session is written inside
    `workspace_transaction(workspace_id)`, where the ordinary policy's `WITH
    CHECK` passes on the row's own terms; a lobby session is written inside
    `lobby_transaction(user_id)`, where `session_lobby` does the same. Everything
    else — the identifier, the lifetime, the user-agent digest — is identical, and
    two functions would have been two places for the lifetime to drift.

    Sign-in calls it, and so does entering a workspace: `commands.enter_workspace`
    deletes the current row and calls this one, because
    `access.session.workspace_id` **cannot be moved in place**. Under the old
    tenant the policy's `WITH CHECK` refuses the new value; under the new one its
    `USING` half cannot see the row to update. That is not a limitation being
    worked around — a fresh session id on every change of tenant is the behaviour
    a re-authentication would have given anyway.

    `record_login` and `rehash_to` are sign-in's two extra writes, threaded here
    rather than performed by the caller so they share this transaction. Both touch
    `access."user"`, which is global and carries no policy (ADR-0045), so they are
    legal inside either context.

    The returned string is the **cookie value** and the one thing in this module
    that must never be logged.
    """
    session_id = _mint_session_id()
    context = (
        workspace_transaction(sessionmaker, workspace_id)
        if workspace_id is not None
        else lobby_transaction(sessionmaker, user_id)
    )

    async with context as db:
        await db.execute(
            ISSUE_SESSION,
            {
                "id": session_id,
                "user_id": user_id,
                "workspace_id": workspace_id,
                "created_at": now,
                "expires_at": now + SESSION_LIFETIME,
                "user_agent_hash": _hash_user_agent(user_agent),
            },
        )
        if record_login:
            await db.execute(RECORD_LOGIN, {"now": now, "user_id": user_id})
        if rehash_to is not None:
            await db.execute(REHASH_PASSWORD, {"password_hash": rehash_to, "user_id": user_id})

    return session_id


@dataclass(frozen=True, slots=True)
class Membership:
    """One row of the workspace chooser: a workspace this person is in, or waiting on.

    `status` is `active` or `pending` and never `removed` — see
    :data:`LOAD_MEMBERSHIP`. `roles` is empty for every pending membership, because
    roles are bound at the moment of approval and not before.

    Frozen and slotted like every value object in `domain.py`, and for the same
    reason: this is the list a session is about to be bound from, so a caller that
    could edit an entry is a caller that could enter a workspace it did not find.
    """

    workspace_id: str
    name: str
    slug: str
    status: MemberStatus
    added_at: datetime
    roles: tuple[Role, ...] = ()


async def list_memberships(
    sessionmaker: async_sessionmaker[AsyncSession], user_id: str
) -> tuple[Membership, ...]:
    """Every workspace this person is in or waiting on, found across a tenant boundary.

    A person's memberships live in a **policied** table, and the caller may have no
    tenant at all — that is the whole shape of the bootstrap problem, and it is now
    the shape of the workspace chooser too. `access.list_workspaces()` is the
    sanctioned enumerator for exactly this (ADR-0051): it returns tenant
    **identifiers**, so every read afterwards runs under ordinary policy rather
    than with it switched off. No fifth `SECURITY DEFINER` function was needed and
    none was added.

    **One query behind two decisions**, which is the point of it being a function
    rather than two. Sign-in counts the active entries to decide whether to bind a
    tenant; `GET /api/v1/auth/workspaces` renders all of them. A separate
    "which workspace does sign-in pick" query would be a second place for the two
    to disagree, and the disagreement would look like a workspace that is in your
    list and cannot be entered.

    Ordered by `(added_at, workspace_id)` — deterministic and stable across
    sign-ins, which is the property OQ-137 asked the old oldest-membership-wins
    rule to keep and which the chooser still wants, so the list does not reshuffle
    itself between visits.

    Cost is one query per workspace in the install, bounded by a number that grows
    with tenants rather than with traffic. It is on the sign-in path, whose budget
    is 500 ms and whose argon2id step already spends 55-70 ms of it. If an install
    ever has enough workspaces for this to matter, the answer is an index on
    `workspace_member (user_id)` and a single `SECURITY DEFINER` read — not a wider
    bypass, and not caching a permission-shaped fact (A-114).
    """
    async with sessionmaker() as db:
        workspace_ids = (await db.execute(LIST_WORKSPACES)).scalars().all()

    found: list[Membership] = []
    for workspace_id in workspace_ids:
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            row = (await db.execute(LOAD_MEMBERSHIP, {"user_id": user_id})).one_or_none()
        if row is None:
            continue
        found.append(
            Membership(
                workspace_id=row.workspace_id,
                name=row.name,
                slug=row.slug,
                status=MemberStatus(row.status),
                added_at=row.added_at,
                roles=tuple(Role(role) for role in row.roles),
            )
        )

    return tuple(sorted(found, key=lambda entry: (entry.added_at, entry.workspace_id)))


async def enter_workspace(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    workspace_id: str,
    current_session_id: str | None,
    current_workspace_id: str | None,
    now: datetime,
    user_agent: str | None = None,
) -> str | None:
    """Move a person into one workspace. Returns the new cookie value, or `None` if refused.

    ADR-0056, and the answer to OQ-137's second option: *"a switch route that ends
    the session and issues another in the chosen workspace"*.

    **Ending and reissuing is forced by the policy, not chosen for hygiene.**
    `access.session.workspace_id` cannot be moved in place by `prope_app`: under
    the old tenant the policy's `WITH CHECK` refuses the new value, and under the
    new tenant its `USING` half cannot see the row to update. What the constraint
    buys is a property worth having anyway — the session id changes whenever the
    tenant does, so a credential captured in one workspace is not a credential in
    the next.

    **The membership check is the authorisation and it is deliberately not
    `may()`.** There is no permission called "may enter this workspace": being an
    active member *is* the authority, which is the same thing
    :func:`list_memberships` reports and the same thing sign-in counts. A `pending`
    membership does not qualify — that is the whole of what pending means — and
    neither does a `removed` one.

    **A refusal is `None` and the caller renders not-found** (A-116). A workspace
    the actor is not an active member of must be indistinguishable from one that
    does not exist: a `403` would confirm the workspace is real, which turns the
    path parameter into an enumeration oracle across tenants.

    **Only the presented session is ended, never every session in the old
    workspace.** Signing out is the act that means *end everything*; this one means
    *this browser is going somewhere else*, and taking a phone offline with it
    would be a surprise nobody asked for. The lobby sessions go too, because a
    lobby session is not scoped to any workspace and leaving one alive would leave
    a second live credential for a context the person has left.

    **The old session is deleted under its OWN tenant, which is why
    `current_workspace_id` is a parameter.** It looks redundant beside
    `current_session_id` and is not: `access.session` is tenant-policied, so a
    `DELETE ... WHERE id = :id` issued inside the *target* workspace's transaction
    matches zero rows when the row belongs to another workspace — silently, because
    a policy filters rather than refuses. That is the same "a missing filter returns
    zero rows" property that makes the tenant seam safe (ADR-0045) working against
    a delete, and it would have left the previous session alive on every
    workspace-to-workspace switch. A session naming no workspace passes `None` and
    is removed by `delete_lobby_sessions` below.

    **Three transactions, ordered so a failure fails closed.** The check runs
    first; the old credential is destroyed second; the new one is minted last. A
    crash between the second and third leaves the person signed out and having to
    sign in again, which is the safe end of the failure — the alternative ordering
    leaves two live credentials for one browser.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        member = (await db.execute(LOAD_ACTIVE_MEMBERSHIP, {"user_id": user_id})).one_or_none()
        if member is None:
            return None

    if current_session_id is not None and current_workspace_id is not None:
        async with workspace_transaction(sessionmaker, current_workspace_id) as db:
            await db.execute(DELETE_SESSION, {"id": current_session_id})

    # Its own transaction, because a lobby row is invisible inside a tenant one —
    # see `delete_lobby_sessions`. This is what ends a lobby session presented to
    # this route, which the delete above deliberately cannot reach.
    await delete_lobby_sessions(sessionmaker, user_id)

    return await issue_session(
        sessionmaker,
        user_id=user_id,
        workspace_id=workspace_id,
        now=now,
        user_agent=user_agent,
    )


async def delete_session(db: AsyncSession, session_id: str) -> None:
    """End one session, on the caller's transaction. Effective immediately.

    No TTL to wait out and no cache to invalidate, because there is nothing to
    invalidate (ADR-0022). The next request presenting this cookie gets the same
    `401` as one presenting a cookie that never existed.
    """
    await db.execute(DELETE_SESSION, {"id": session_id})


async def delete_user_sessions(db: AsyncSession, user_id: str) -> int:
    """End every session this user holds **in the caller's tenant**, and count them.

    Tenant-scoped, because `access.session` is policied and this runs on an
    ordinary transaction. A-151's tombstone therefore calls it once per workspace
    the person belonged to, which is also why it returns a count: the tombstone
    asserts that the total across workspaces is every session that existed, and a
    function that swallowed the number would have made that assertion impossible
    to write.
    """
    result = await db.execute(DELETE_USER_SESSIONS, {"user_id": user_id})
    return result.rowcount or 0


async def delete_lobby_sessions(
    sessionmaker: async_sessionmaker[AsyncSession], user_id: str
) -> int:
    """End every **workspace-less** session this person holds. ADR-0056.

    The same statement :func:`delete_user_sessions` issues, under
    `lobby_transaction` instead of a tenant one — so the `session_lobby` policy
    narrows it to rows whose `workspace_id` is NULL and whose owner is this person,
    and a tenant session is untouched.

    **It takes a sessionmaker where its sibling takes a session**, and the
    asymmetry is the policy's rather than a style choice: a lobby row is invisible
    inside any tenant transaction, so there is no caller's transaction it could
    join. Every caller of this one is therefore doing two things in two
    transactions, and that is stated at each call site rather than hidden here.

    Called when a person **enters** a workspace — the lobby session they were
    holding is spent, and leaving it alive would leave a second live credential for
    a context they have left — and on sign-out, where the cookie is being cleared
    and an orphaned row would otherwise sit until expiry.
    """
    async with lobby_transaction(sessionmaker, user_id) as db:
        result = await db.execute(DELETE_USER_SESSIONS, {"user_id": user_id})
    return result.rowcount or 0

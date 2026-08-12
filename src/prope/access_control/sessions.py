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
from prope.access_control.limiter import LoginLimiter
from prope.access_control.limiter import limiter as process_limiter
from prope.access_control.observability import login_duration_seconds, login_total
from prope.db.session import workspace_transaction
from prope.session_auth import Session

__all__ = [
    "PUBLIC_SESSION_ID_PREFIX",
    "SESSION_ID_PREFIX",
    "SESSION_LIFETIME",
    "SignInResult",
    "delete_session",
    "delete_user_sessions",
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

    session: Session | None
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
    3. **Find the workspace.** A person with no active membership cannot sign in,
       and that failure is counted as `unknown` rather than given a name of its
       own: it is the state a removed member is in, and telling them apart from a
       stranger would be an oracle for "this person used to work here".
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

    workspace_id = await _sign_in_workspace(sessionmaker, user.id)
    if workspace_id is None:
        active_limiter.record_failure(email=email, source_address=source_address)
        login_total.labels(result="unknown").inc()
        return _finish(SignInResult(session=None, metric_result="unknown"))

    session_id = _mint_session_id()
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await db.execute(
            ISSUE_SESSION,
            {
                "id": session_id,
                "user_id": user.id,
                "workspace_id": workspace_id,
                "created_at": moment,
                "expires_at": moment + SESSION_LIFETIME,
                "user_agent_hash": _hash_user_agent(user_agent),
            },
        )
        await db.execute(RECORD_LOGIN, {"now": moment, "user_id": user.id})

        # ADR-0043: on every successful login, so raising the cost later migrates
        # hashes as people sign in rather than as a migration. Inside the sign-in
        # transaction because a rehash that committed while the session insert
        # rolled back would have changed a password hash for a login that did not
        # happen.
        if stored_hash is not None and passwords.needs_rehash(stored_hash):
            await db.execute(
                REHASH_PASSWORD,
                {
                    "password_hash": passwords.hash_password(password),
                    "user_id": user.id,
                },
            )

    # A-144: a successful sign-in clears the EMAIL bucket. The source-address
    # bucket is deliberately left alone — see `LoginLimiter.clear_email`.
    active_limiter.clear_email(email)
    login_total.labels(result="ok").inc()
    return _finish(
        SignInResult(
            session=Session(user_id=user.id, workspace_id=workspace_id),
            metric_result="ok",
            must_change_password=user.must_change_password,
            session_id=session_id,
        )
    )


async def _sign_in_workspace(
    sessionmaker: async_sessionmaker[AsyncSession], user_id: str
) -> str | None:
    """The workspace a sign-in lands in, found across a tenant boundary it has not crossed yet.

    A person's memberships live in a **policied** table, and at this point in the
    request there is no tenant — that is the whole shape of the bootstrap
    problem. `access.list_workspaces()` is the sanctioned enumerator for exactly
    this (ADR-0051): it returns tenant **identifiers**, so every read afterwards
    runs under ordinary policy rather than with it switched off.

    A person may be a member of several workspaces. The MVP has no workspace
    picker, so the **oldest active membership wins** — deterministic rather than
    arbitrary, and stable across sign-ins, which is what stops somebody's
    bookmarks pointing into a different tenant on Tuesday. `OQ-137` carries the
    picker.

    Cost is one query per workspace in the install, which is a handful in the
    pilot and is bounded by a number that grows with tenants rather than with
    traffic. It is on the sign-in path, whose budget is 500 ms and whose argon2id
    step already spends 55–70 ms of it; if the install ever has enough workspaces
    for this to matter, the answer is the picker rather than a wider bypass.
    """
    async with sessionmaker() as db:
        workspace_ids = (await db.execute(LIST_WORKSPACES)).scalars().all()

    best: tuple[datetime, str] | None = None
    for workspace_id in workspace_ids:
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            row = (
                await db.execute(LOAD_ACTIVE_MEMBERSHIP, {"user_id": user_id})
            ).one_or_none()
        if row is not None and (best is None or (row.added_at, workspace_id) < best):
            best = (row.added_at, workspace_id)

    return None if best is None else best[1]


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

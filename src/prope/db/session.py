"""The tenant seam (D-08). One workspace, one transaction (ADR-0040).

This is the single place a tenant identifier reaches SQL, and every repository
in all eight modules is written against it. Three requirements are not obvious
and each one is the difference between a working guarantee and a broken one.

**The identifier is bound, never assembled.** PostgreSQL's configuration
assignment statement takes string constants, identifiers and numbers — not
bind parameters. So the obvious ``SET LOCAL app.workspace_id = :ws`` will not
bind, and the tempting repair is to build the statement by interpolation. That
would be an injection site on a value which, from phase 2 onward, arrives
inside a broker payload. ``set_config`` is an ordinary function call and
parameterises normally. There is no interpolation of any kind in this module,
and a source gate asserts it —
``tests/architecture/test_no_sql_interpolation.py`` parses every module under
``src/prope/`` and requires every ``text(...)`` argument to be a plain string
constant. The gate is a walk over the source rather than a claim, because a
runtime test can only prove that the inputs it happened to try were safe.

**The transaction is opened first.** A transaction-local setting issued outside
a transaction block emits a warning and otherwise has no effect: it would
protect nothing while looking like it protected something. The context manager
owns both operations so the order cannot be got wrong at a call site.

**The workspace is a constructor argument, not a setter.** ADR-0040 requires
that a batch is grouped by workspace and that each transaction covers exactly
one. There is deliberately no method that could set a second workspace inside
an open transaction.

**Three settings, one tenant.** Revision 0022 adds ``app.user_id`` and the
``app.invite_*`` pair, and none of the three is a tenant: each is read by
exactly one named exception policy in the ``access`` schema, and no other table
in the product is scoped by any of them. They exist for the two reads that
happen *before* a tenant is known — a person signing in who belongs nowhere yet,
and a person presenting an invitation whose workspace they cannot name. Each has
its own context manager below, so "which policies can this transaction reach"
is answered by the function a call site chose rather than by which settings
somebody remembered to issue.

Note on test isolation: do not wrap tests in an outer transaction and roll
back. That turns the ``session.begin()`` below into a savepoint, and a
transaction-local setting is scoped to the transaction rather than the
savepoint — so tenant A's context survives into tenant B's call inside the same
test. Truncate between tests instead.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

#: Sets the tenant for the current transaction only. The third argument is what
#: makes it transaction-local; the second is a bound parameter.
SET_TENANT = text("SELECT set_config('app.workspace_id', :ws, true)")

#: Revision 0022's second GUC, and **it is not a tenant**. Exactly one policy in
#: the product reads it — ``session_lobby`` on ``access.session`` — and no other
#: table may ever be scoped by it. It exists because a workspace-less session has
#: no tenant to be scoped by and still must be scoped by *something*: without it
#: the row holding a bearer credential would either be invisible to the runtime
#: role entirely (so unwritable) or visible to every tenant (so harvestable).
SET_ACTOR = text("SELECT set_config('app.user_id', :uid, true)")

#: Revision 0022's third and fourth. Neither is a tenant either, and both are
#: read by one ``FOR SELECT`` policy on ``access.workspace_invite``.
#:
#: The point of scoping a read by *the secret the caller presented* is not that
#: it permits the read — it is that it bounds what the read can return. Inside
#: :func:`invite_lookup_transaction` a ``SELECT`` with no ``WHERE`` yields at
#: most the row whose code was actually typed, so "enumerate every live
#: invitation" is not a statement anybody can write by forgetting a clause.
SET_INVITE_CODE_HASH = text("SELECT set_config('app.invite_code_hash', :digest, true)")
SET_INVITE_EMAIL = text("SELECT set_config('app.invite_email', :email, true)")


@asynccontextmanager
async def workspace_transaction(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
) -> AsyncIterator[AsyncSession]:
    """Open a transaction carrying exactly one workspace's tenant context.

    A query issued on a session obtained any other way sees zero rows, because
    the policy predicate compares against a setting that was never set. That is
    the inversion ADR-0035 is built on, and it is asserted rather than assumed.
    """
    async with sessionmaker() as session:
        async with session.begin():
            await session.execute(SET_TENANT, {"ws": workspace_id})
            yield session


@asynccontextmanager
async def lobby_transaction(
    sessionmaker: async_sessionmaker[AsyncSession],
    user_id: str,
) -> AsyncIterator[AsyncSession]:
    """Open a transaction that can reach **one person's workspace-less session** and nothing else.

    ADR-0056. The only rows this context admits are ``access.session`` rows whose
    ``workspace_id`` is NULL and whose ``user_id`` is the one passed here. Every
    tenant-policied table in the product answers **zero rows** inside it, because
    ``app.workspace_id`` is never set — which is the same inversion
    :func:`workspace_transaction` relies on, arriving from the other direction.

    **It is deliberately not a weaker tenant context.** Nothing here can read a
    prompt, a member list, or another person's lobby session; the one policy that
    admits anything under this GUC is ``session_lobby``, and
    ``tests/security`` asserts that no other policy in the schema mentions
    ``app.user_id``.

    The workspace is a constructor argument on the sibling above so that a second
    tenant cannot be set inside one transaction. ``user_id`` is one here for the
    same reason: a lobby transaction is one person's, for its whole life.
    """
    async with sessionmaker() as session:
        async with session.begin():
            await session.execute(SET_ACTOR, {"uid": user_id})
            yield session


@asynccontextmanager
async def invite_lookup_transaction(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    code_hash: str | None = None,
    email: str | None = None,
) -> AsyncIterator[AsyncSession]:
    """Open a transaction that can read the invitation a caller has **presented**, and no other.

    ADR-0057. Redeeming a code and claiming an email reservation are both
    tenant-less reads: the caller does not know which workspace they are asking
    about — finding that out is the whole point of the read — so no
    ``app.workspace_id`` can be set before it.

    **Read-only in the strong sense**: ``invite_redeem`` is a ``FOR SELECT``
    policy, so no INSERT, UPDATE or DELETE is expressible in this context on any
    table in the product. Everything the caller does *next* — the pending
    membership, the use count, the history event — happens inside a
    :func:`workspace_transaction` on the workspace the row just named, under
    ordinary policy.

    Passing neither argument yields a context that can read **nothing**, which is
    the correct answer to a caller that named no secret rather than an error worth
    raising: the policy predicate is NULL on both sides and admits no row.

    Both values are bound parameters. ``code_hash`` is a digest and never the
    code; ``email`` is the address the person is registering with, which they
    supplied themselves.
    """
    async with sessionmaker() as session:
        async with session.begin():
            if code_hash is not None:
                await session.execute(SET_INVITE_CODE_HASH, {"digest": code_hash})
            if email is not None:
                await session.execute(SET_INVITE_EMAIL, {"email": email})
            yield session

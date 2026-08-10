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
and a source gate asserts it.

**The transaction is opened first.** A transaction-local setting issued outside
a transaction block emits a warning and otherwise has no effect: it would
protect nothing while looking like it protected something. The context manager
owns both operations so the order cannot be got wrong at a call site.

**The workspace is a constructor argument, not a setter.** ADR-0040 requires
that a batch is grouped by workspace and that each transaction covers exactly
one. There is deliberately no method that could set a second workspace inside
an open transaction.

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

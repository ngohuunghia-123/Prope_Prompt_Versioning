"""BR-03's runtime detector, and the honest statement of what it can and cannot see.

`RegistryUnapprovedPointer` is the most important alert in the product: a
released pointer naming a revision nobody approved means production is serving
prompt text nobody approved, which is *"the single failure that makes the whole
product worthless"*. The lock file specifies it as a query — *"the Success-metric
SQL (released pointer whose revision status != Approved) returns any row"* — and
Prometheus cannot run SQL, so something in Prope has to turn that query into a
series.

**Three constraints shape what that something can be, and all three are other
people's decisions.**

*This module has no scheduled job and no queue consumer*, by its own
`deployment_target`, and inventing one here would be inventing a component with
its own runbook (A-012).

*The runtime role cannot see across tenants.* The query is install-wide, and
`prope_app` is subject to the tenant policy — with no `app.workspace_id` set it
returns **zero rows**, which for a must-stay-zero alert is the worst possible
answer: indistinguishable from healthy. The role that could run it in one
statement is `prope_report`, which carries `BYPASSRLS` and which
``prope.app.refuse_a_privileged_credential`` refuses to let this process hold.

*So the sweep enumerates tenants and reads each one under its own policy*, using
ADR-0051's sanctioned enumerator through access-control's API. Identifiers cross
the boundary; every actual read below runs with the policy on.

**It runs once, at startup, and that window is stated rather than hidden.** The
constraint ``fk_prompt_property_released_version_id`` makes the condition
unreachable through any application path, so what is left for this to catch is a
migration that dropped or deferred it, a restore from a dump taken before it
existed, or a direct write as ``prope_migrate`` — and the first two are followed
by a process restart under ADR-0031, which is the moment this runs. A direct
write by a human is not caught until the next restart. That is a real gap and it
is the price of not adding a scheduled job; the compensating control is that the
constraint means there is nothing to catch.
"""

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.seams import list_workspace_ids
from prope.db.session import workspace_transaction
from prope.prompt_registry.observability import unapproved_pointer_rows

log = structlog.get_logger(__name__)

__all__ = ["UNAPPROVED_POINTERS", "count_unapproved_pointers", "refresh_unapproved_pointer_gauge"]

#: The Success-metric query, one workspace at a time.
#:
#: The join is an INNER join on purpose. A pointer naming a ``version_id`` that
#: does not exist at all would not appear here — and it cannot exist, because the
#: same foreign key that checks the status also checks the reference. Widening
#: this to a LEFT join would be testing for a state the constraint makes
#: unreachable by a second mechanism, which is how a query stops being readable
#: as the thing it is checking.
UNAPPROVED_POINTERS = text(
    """
    SELECT count(*)
    FROM   registry.prompt_property AS p
    JOIN   registry.revision AS r ON r.version_id = p.released_version_id
    WHERE  r.status <> 'Approved'
    """
)


async def count_unapproved_pointers(db: AsyncSession) -> int:
    """The count for the workspace whose tenant context this session carries."""
    return int(await db.scalar(UNAPPROVED_POINTERS) or 0)


async def refresh_unapproved_pointer_gauge(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> int:
    """Sweep every workspace, set the gauge to the total, and return it.

    **Never raises.** A composition root calls this during startup, and a
    reconciliation that could not run is not a reason to refuse to serve — the
    gauge stays at whatever it was (0 at import, which is a live series either
    way) and the failure is logged. The alternative would let a transient
    database blip during startup take the gateway down to protect a path that is
    working, which is the same argument ``/readyz`` makes about the broker.

    The log line carries the count and the exception's class, and nothing else:
    at this depth an exception's message can quote a connection string (A-046).
    """
    try:
        workspace_ids = await list_workspace_ids(sessionmaker)
        total = 0
        for workspace_id in workspace_ids:
            async with workspace_transaction(sessionmaker, workspace_id) as db:
                total += await count_unapproved_pointers(db)
    except Exception as error:
        log.warning("prompt_registry.reconciliation_failed", reason=type(error).__name__)
        return -1

    unapproved_pointer_rows.set(total)
    if total:
        log.warning("prompt_registry.unapproved_pointer", outcome="found")
    return total

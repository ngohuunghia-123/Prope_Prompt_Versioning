"""INT-034 — this module's one inbound seam, and it is deliberately one.

Re-export only. ``record_observation`` lives in ``repository.py``; nothing else
in this package is callable from outside it, because nothing else needs to be.
The management reads are reached through this module's own routes and the
adoption write is reached through **prompt-registry's** routes, which is
ADR-0060's whole shape: this module hands a person a proposal and the person
posts it somewhere else.

**This seam takes the SESSIONMAKER, not the caller's ``AsyncSession``** — the one
place in Prope where that is the right way round, and prompt-registry's rule
(*every seam takes the caller's session*) does not apply because the reason
behind that rule is absent. There, sharing a transaction is load-bearing: a
release row, its history append and the pointer write must land together. Here
there is nothing to land with. The gateway calls this from a background task
**after** the response is flushed, so the only transaction available is one
opened for this write and nothing else.

Taking the sessionmaker is what lets the seam keep INT-034's two declared
properties itself, rather than asking every caller to remember them:

* **It never raises.** A-155's write is best-effort by design — a lost
  observation costs a counter where a lost call record costs money — and a seam
  that raised would turn that into an unhandled exception in a background task
  nobody is watching. The failure is counted and abandoned here, once, instead of
  in a ``try`` block at each call site that could quietly stop matching.
* **It owns its metrics.** ``write_duration_seconds`` and ``write_failed_total``
  are this module's, declared in its own ``observability`` module, and the
  gateway does not import them — the gateway's import allow-list is what makes
  that a rule rather than a preference.

**There is no outbound seam and no queue.** A-155 chose a direct write over a
second broker queue, which the project has rejected twice on merit; the write is
small, idempotent under the fingerprint unique constraint, and already off the
caller's latency path. What it costs is that an observation can be lost when the
process dies mid-task, and that is priced: the next call with the same body
re-creates the group, and the sighting count is approximate by construction
anyway — it counts what Prope saw, not what the product sent.
"""

import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.prompt_observation import repository
from prope.prompt_observation.domain import (
    AdoptionProposal,
    ObservationDraft,
    ObservationRow,
    ObservationStatus,
    SightingRow,
)
from prope.prompt_observation.observability import write_duration_seconds, write_failed_total

log = structlog.get_logger(__name__)

__all__ = [
    "AdoptionProposal",
    "ObservationDraft",
    "ObservationRow",
    "ObservationStatus",
    "SightingRow",
    "record_observation",
]


async def record_observation(
    sessionmaker: async_sessionmaker[AsyncSession], draft: ObservationDraft
) -> str | None:
    """INT-034. File one forwarded call against its fingerprint group.

    Returns the observation's id, ``None`` when the call carried no system
    message and there was therefore no prompt in it to observe, and ``None``
    again when the write failed — the caller cannot act on the difference, which
    is why they are the same value here and two different log lines.

    **Never raises**, and the bare ``except Exception`` is the contract rather
    than laziness. There is no caller left to tell: the response was flushed
    before this ran. The alternatives are a counter or an exception propagating
    into a background task, and only one of those is visible on a dashboard.
    """
    started = time.perf_counter()
    try:
        async with workspace_transaction(sessionmaker, draft.workspace_id) as db:
            observation_id = await repository.record_observation(db, draft)
    except Exception as error:
        write_failed_total.inc()
        log.warning(
            "observation.abandoned",
            call_id=draft.call_id,
            workspace_id=draft.workspace_id,
            reason=type(error).__name__,
        )
        return None
    finally:
        write_duration_seconds.observe(time.perf_counter() - started)

    # No `observed` flag: `observation_id` is None or it is not, and a boolean
    # restating that would be a second field to keep in step with the first.
    log.debug(
        "observation.written",
        call_id=draft.call_id,
        workspace_id=draft.workspace_id,
        observation_id=observation_id,
    )
    return observation_id

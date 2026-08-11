"""ADR-0038's action registry, as an immutable process-lifetime mapping."""

from collections.abc import Mapping
from types import MappingProxyType

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.domain import RegisteredAction

#: **No ``WHERE`` clause, and the absence is the point.** Every other statement
#: in Prope carries a ``workspace_id`` predicate alongside the tenant policy; the
#: registry has no tenant column at all (D-56), so there is nothing to write out
#: — and that absence is exactly what lets ``registered_actions()``'s CI
#: consumer, a test with no tenant context, see rows at all.
LOAD_REGISTRY = text(
    """
    SELECT action, target_type, detail_keys, requires_reason, writing_module
    FROM   history.history_action_registry
    """
)


async def load_action_registry(session: AsyncSession) -> Mapping[str, RegisteredAction]:
    """ADR-0038's mapping: read once, immutable, no TTL and no invalidation.

    **``session`` carries NO tenant context, and that is the assertion.** Were
    the registry ever made tenant-scoped, ADR-0035's inversion would return zero
    rows here rather than raising — and an empty vocabulary makes every append
    fail with ``unknown_action`` while AC-6 compares two empty sets and stays
    green.

    Phase 4 calls this from tests; **Phase 5 owns loading it once at process
    start** into ``app`` and ``worker``. Nothing here is a module global,
    deliberately, so Phase 5 introduces the global rather than inheriting a
    mutable one somebody already reached for.

    Raises ``RuntimeError`` on an empty table — see below.
    """
    rows = (await session.execute(LOAD_REGISTRY)).all()
    if not rows:
        # NOT HistoryAppendRejected: an empty registry is a migration that did
        # not run, not one bad append, and ``pricing.resolve_price``'s "absence
        # is a complete answer" does not transfer. With Phase 5's load at process
        # start this becomes a startup failure, which is the correct shape.
        raise RuntimeError(
            "history.history_action_registry is empty: revision 0005 seeds 31 rows, so an "
            "empty vocabulary means the migration has not been applied to this database"
        )

    # asyncpg returns text[] as list[str]; frozenset is what the allow-list check
    # wants and what makes the mapping immutable below the top level.
    loaded = {
        action: RegisteredAction(
            action=action,
            target_type=target_type,
            detail_keys=frozenset(detail_keys),
            requires_reason=requires_reason,
            writing_module=writing_module,
        )
        for action, target_type, detail_keys, requires_reason, writing_module in rows
    }
    # A view, so the dict must not outlive this frame — otherwise "immutable
    # after load" is a claim about a name rather than about an object.
    return MappingProxyType(loaded)

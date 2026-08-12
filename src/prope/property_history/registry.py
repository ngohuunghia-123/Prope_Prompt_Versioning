"""ADR-0038's action registry, as an immutable process-lifetime mapping."""

from collections.abc import Mapping
from types import MappingProxyType

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.property_history.domain import RegisteredAction

#: WHY no ``WHERE`` clause: the registry has no tenant column at all (D-56),
#: which is what lets a no-tenant CI consumer see rows.
LOAD_REGISTRY = text(
    """
    SELECT action, target_type, detail_keys, requires_reason, writing_module
    FROM   history.history_action_registry
    """
)


async def load_action_registry(session: AsyncSession) -> Mapping[str, RegisteredAction]:
    """ADR-0038's mapping: read once, immutable, no TTL. ``session`` must carry
    NO tenant context (D-56); an empty table raises rather than answering."""
    rows = (await session.execute(LOAD_REGISTRY)).all()
    if not rows:
        # NOT HistoryAppendRejected: an empty registry is a migration that did
        # not run, not one bad append.
        raise RuntimeError(
            "history.history_action_registry is empty: revision 0005 seeds 31 rows, so an "
            "empty vocabulary means the migration has not been applied to this database"
        )

    # frozenset is what makes the mapping immutable below the top level.
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
    # A view, so the dict must not outlive this frame.
    return MappingProxyType(loaded)


async def registered_actions(session: AsyncSession) -> tuple[RegisteredAction, ...]:
    """The seeded vocabulary, read live off the TABLE and never the cache — INT-008.

    ADR-0038 requires the table read: a test checking the cache would assert
    nothing about what ``append()`` accepts after the next migration. The
    no-tenant session and the fifth column are widenings, per OQ-034.
    """
    mapping = await load_action_registry(session)
    return tuple(sorted(mapping.values(), key=lambda row: row.action))


#: ADR-0038's process-lifetime cache: a ``MappingProxyType``, never a ``dict``,
#: and no TTL — a refresh path was rejected by name.
_REGISTRY: Mapping[str, RegisteredAction] | None = None


def install_registry(registry: Mapping[str, RegisteredAction]) -> None:
    """Fill the process cache, from a composition root. A second call replaces the
    first, which keeps ``run_worker`` and the ASGI lifespan drivable twice."""
    global _REGISTRY
    _REGISTRY = registry


def registered_registry() -> Mapping[str, RegisteredAction]:
    """The installed vocabulary. Raises rather than answering an empty mapping,
    which would fail every append with ``unknown_action`` — one page per
    append, blaming a caller for a composition bug."""
    if _REGISTRY is None:
        raise RuntimeError(
            "the action registry has not been installed in this process: "
            "prope.app's lifespan and prope.worker.run_worker each call "
            "install_registry(await load_action_registry(session)) at startup, and nothing "
            "else may"
        )
    return _REGISTRY


def reset_registry() -> None:
    """Clear the cache. For the test rig and for nothing else — reset-plus-install
    is the refresh path ADR-0038 rejects by name."""
    global _REGISTRY
    _REGISTRY = None

"""A-046 for property-history: a marker in ``reason`` or in ``details`` reaches no log line.

**This module's A-046 position is sharper than any other module's.** The lock
forbids logging two columns this module writes, and each is forbidden for a
different reason: ``reason`` is user-authored free text in Vietnamese that may
quote whatever its author was looking at, and ``details`` is the one column in
Prope with no fixed shape, written by five modules. Both are allow-listed
*into the table* (A-124) and neither is allow-listed *into a log line*.

**Whole records, not fields.** Every assertion below `repr`s the whole
captured log record rather than inspecting one field, in
``tests/broker/test_publish_confirm_failures.py:200-237``'s shape — a
per-field assertion tests the field somebody thought of, and the leak that
matters is the field nobody thought of.

**This file is the first thing in the project that reads ``LOGGABLE_FIELDS``**
(``src/prope/observability.py``), since the set was written in Phase 2. What
that buys: every key this module actually logs, on the paths this module
actually exercises, is checked against the allow-list. What it does not buy:
a log call on a path no test runs is invisible to it, and a dynamically-built
``**fields`` payload would walk straight past a stricter, source-level gate
too. That stricter gate — an AST walk over every structlog call site under
``src/prope/`` — is routed to Phase 6, which owns AC-8 (the full-corpus
content assertion); it goes red on arrival against
``src/prope/call_ledger/schemas.py:442``, where ``request_id`` is logged and
is not in ``LOGGABLE_FIELDS`` (see ``.planning/WINDOWS.md``).
"""

import pytest
import structlog
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.db.session import workspace_transaction
from prope.observability import LOGGABLE_FIELDS
from prope.property_history.append import record_event
from prope.property_history.domain import (
    ActorType,
    HistoryAppendRejected,
    HistoryEventDraft,
    RejectionReason,
)
from tests.property_history import ACTOR_ID, TARGET_ID, WORKSPACE_A, day, load_registry

REASON_MARKER = "zzmarkerzz-reason-4ba17c"
DETAIL_MARKER = "zzmarkerzz-detail-9f21ab"

SELECT_EVENT = text("SELECT reason, details FROM history.history_event WHERE id = :id")

#: capture_logs() injects these two keys itself; they are not this module's
#: output and are excluded from the allow-list check by name rather than
#: silently.
CAPTURE_LOGS_OWN_KEYS = frozenset({"event", "log_level"})


def _every_metric_label_value() -> list[str]:
    """Every label value currently in the registry, across every metric.

    Copied in shape from ``tests/broker/test_publish_confirm_failures.py``:
    collected wholesale rather than per-metric, because the rule is that
    content reaches NO label and a per-metric list is a list somebody has to
    remember to extend.
    """
    values: list[str] = []
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            values.extend(str(v) for v in sample.labels.values())
    return values


async def test_a_marker_in_reason_and_in_details_survives_a_successful_append_and_reaches_nothing(
    app_sessionmaker, migrate_engine: AsyncEngine
):
    """Stored, but never logged — the two are distinguished, not conflated."""
    registry = await load_registry(app_sessionmaker)
    draft = HistoryEventDraft(
        workspace_id=WORKSPACE_A,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        action="revision_released",
        target_type="revision",
        target_id=TARGET_ID,
        occurred_at=day(5),
        reason=REASON_MARKER,
        details={
            "version_id": DETAIL_MARKER,
            "previous_version_id": "ver_01J0000000000000000000000",
            "break_glass": False,
        },
    )

    with structlog.testing.capture_logs() as captured:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            event_id = await record_event(session, draft, registry)

    async with migrate_engine.begin() as connection:
        row = (await connection.execute(SELECT_EVENT, {"id": event_id})).one_or_none()
    assert row is not None, "the append must actually have happened, or this proves nothing"

    assert captured, "a successful append must log SOMETHING, or the assertion is vacuous"

    for record in captured:
        rendered = repr(record)
        assert REASON_MARKER not in rendered
        assert DETAIL_MARKER not in rendered
    for value in _every_metric_label_value():
        assert REASON_MARKER not in value
        assert DETAIL_MARKER not in value

    # "Never logged" is distinguished from "never stored": both markers ARE
    # in the row, so the log absence above is not just the module dropping
    # the values entirely.
    stored_reason, stored_details = row
    assert stored_reason == REASON_MARKER
    assert stored_details["version_id"] == DETAIL_MARKER


async def test_a_marker_in_a_rejected_appends_details_reaches_nothing_and_the_key_name_does(
    app_sessionmaker,
):
    """The refusal path the lock file calls out by name: the key name logs, the value never does."""
    registry = await load_registry(app_sessionmaker)
    draft = HistoryEventDraft(
        workspace_id=WORKSPACE_A,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        action="revision_approved",
        target_type="revision",
        target_id=TARGET_ID,
        occurred_at=day(5),
        details={"an_unregistered_key": DETAIL_MARKER},
    )

    with structlog.testing.capture_logs() as captured:
        with pytest.raises(HistoryAppendRejected) as excinfo:
            async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
                await record_event(session, draft, registry)

    assert excinfo.value.reason is RejectionReason.UNKNOWN_DETAIL_KEY
    assert captured, "a refused append must log SOMETHING, or the assertion is vacuous"

    for record in captured:
        assert DETAIL_MARKER not in repr(record)
    for value in _every_metric_label_value():
        assert DETAIL_MARKER not in value

    assert any("an_unregistered_key" in repr(record) for record in captured), (
        "a rejected append logs the action and the offending key NAME"
    )


async def test_a_marker_in_reason_reaches_nothing_on_the_refusal_path(app_sessionmaker):
    """A refusal at check one issues no SQL. A naive whole-draft log would leak here."""
    registry = await load_registry(app_sessionmaker)
    draft = HistoryEventDraft(
        workspace_id=WORKSPACE_A,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        action="not_a_registered_action",
        target_type="revision",
        target_id=TARGET_ID,
        occurred_at=day(5),
        reason=REASON_MARKER,
    )

    with structlog.testing.capture_logs() as captured:
        with pytest.raises(HistoryAppendRejected) as excinfo:
            async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
                await record_event(session, draft, registry)

    assert excinfo.value.reason is RejectionReason.UNKNOWN_ACTION
    assert captured, "a refused append must log SOMETHING, or the assertion is vacuous"

    for record in captured:
        assert REASON_MARKER not in repr(record)
    for value in _every_metric_label_value():
        assert REASON_MARKER not in value


async def test_every_logged_key_is_in_the_allow_list(app_sessionmaker):
    """The assertion that turns the allow-list from documentation into a rule."""
    registry = await load_registry(app_sessionmaker)
    success_draft = HistoryEventDraft(
        workspace_id=WORKSPACE_A,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        action="revision_approved",
        target_type="revision",
        target_id=TARGET_ID,
        occurred_at=day(5),
    )
    refused_draft = HistoryEventDraft(
        workspace_id=WORKSPACE_A,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        action="not_a_registered_action",
        target_type="revision",
        target_id=TARGET_ID,
        occurred_at=day(5),
    )

    with structlog.testing.capture_logs() as captured:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
            await record_event(session, success_draft, registry)
        try:
            async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
                await record_event(session, refused_draft, registry)
        except HistoryAppendRejected:
            pass

    assert captured
    for record in captured:
        offending = set(record) - LOGGABLE_FIELDS - CAPTURE_LOGS_OWN_KEYS
        assert not offending, (
            f"{offending} logged by property-history is not in LOGGABLE_FIELDS — "
            "either it should not be logged, or the allow-list has not been told "
            "about it. Both are answered in src/prope/observability.py, never by "
            "relaxing this test."
        )

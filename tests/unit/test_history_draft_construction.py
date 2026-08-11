"""``HistoryEventDraft.__post_init__``'s three refusals, and what class they carry.

Two of the three restate a database CHECK in Python so the caller meets a
sentence naming the field rather than a constraint name it cannot act on. That
makes them audit refusals, which is why the class is
:class:`HistoryDraftInvalid` and not ``ValueError``: a draft is assembled inside
the caller's own request validation, and an ``except ValueError`` there would
swallow the refusal and commit the state change without its event.

The class assertion is the load-bearing one. ``pytest.raises(ValueError)`` would
still pass against ``HistoryDraftInvalid``'s predecessor and against every future
regression back to it, so each test names the class and then asserts that a
``ValueError`` handler would **not** have caught it.
"""

import datetime as dt

import pytest
from prometheus_client import REGISTRY

from prope.property_history.domain import (
    MAX_REASON_CHARACTERS,
    ActorType,
    HistoryDraftInvalid,
    HistoryEventDraft,
)
from tests.unit import WORKSPACE_A, day

ACTOR_ID = "usr_01J000000000000000000001"
TARGET_ID = "rev_01J000000000000000000001"


def draft(**overrides) -> HistoryEventDraft:
    values = {
        "workspace_id": WORKSPACE_A,
        "actor_type": ActorType.USER,
        "actor_id": ACTOR_ID,
        "action": "revision_approved",
        "target_type": "revision",
        "target_id": TARGET_ID,
        "occurred_at": day(5),
    }
    values.update(overrides)
    return HistoryEventDraft(**values)


def test_a_naive_occurred_at_is_refused():
    with pytest.raises(HistoryDraftInvalid) as excinfo:
        draft(occurred_at=dt.datetime(2026, 1, 5, 12, 0, 0))

    assert "occurred_at" in str(excinfo.value)
    assert not isinstance(excinfo.value, ValueError)


def test_a_user_actor_with_no_actor_id_is_refused():
    """``ck_history_event_actor_id_present_unless_system``, restated in Python."""
    with pytest.raises(HistoryDraftInvalid) as excinfo:
        draft(actor_id=None)

    assert "actor_id" in str(excinfo.value)
    assert not isinstance(excinfo.value, ValueError)


def test_a_system_actor_may_be_anonymous():
    """The permitted half of the same rule, and the only ``ActorType.SYSTEM`` draft."""
    event = draft(actor_type=ActorType.SYSTEM, actor_id=None)

    assert event.actor_type is ActorType.SYSTEM
    assert event.actor_id is None


def test_a_reason_over_the_cap_is_refused_and_the_cap_itself_is_accepted():
    """``ck_history_event_reason_length``, restated in Python. Characters, not bytes."""
    assert draft(reason="ứ" * MAX_REASON_CHARACTERS).reason is not None

    with pytest.raises(HistoryDraftInvalid) as excinfo:
        draft(reason="ứ" * (MAX_REASON_CHARACTERS + 1))

    assert str(MAX_REASON_CHARACTERS) in str(excinfo.value)
    assert not isinstance(excinfo.value, ValueError)


def test_a_refused_draft_counts_no_append_rejection():
    """D-63: three labels, and construction is not an append.

    The lock's alert pages on every increment, so a draft that never reached
    ``append()`` incrementing one would be a page for a request that was refused
    before it started.
    """
    before = [
        REGISTRY.get_sample_value(
            "prope_property_history_append_rejected_total", {"reason": reason}
        )
        or 0.0
        for reason in ("unknown_action", "unknown_detail_key", "missing_reason")
    ]

    with pytest.raises(HistoryDraftInvalid):
        draft(actor_id=None)

    after = [
        REGISTRY.get_sample_value(
            "prope_property_history_append_rejected_total", {"reason": reason}
        )
        or 0.0
        for reason in ("unknown_action", "unknown_detail_key", "missing_reason")
    ]
    assert after == before

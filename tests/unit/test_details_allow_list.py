"""AC-5's pure half: ``check_event`` refuses before any SQL is issued.

"Unit" names the SCOPE of the assertion rather than the absence of an engine
(D-02) — and this file genuinely has no engine in it, because raising before any
statement is the property under test.

The registry here is INVENTED, and the action names say so. It is deliberately
not the seeded vocabulary: ``tests/conftest.py``'s ``history_action_registry``
fixture installs the thirty-seven real rows for every other test, and nobody should
be able to mistake this file for a second source of those names.

``check_event`` keeps its explicit ``registry`` parameter where ``append`` reads
the process cache — that parameter is what lets this file build its own mapping.
"""

from types import MappingProxyType

import pytest
from prometheus_client import REGISTRY

from prope.property_history.append import check_event
from prope.property_history.domain import (
    ActorType,
    HistoryAppendRejected,
    HistoryEventDraft,
    RegisteredAction,
    RejectionReason,
)
from tests.unit import WORKSPACE_A, day

ACTOR_ID = "usr_01J000000000000000000001"
TARGET_ID = "fix_01J000000000000000000001"

#: The offending VALUE. Distinctive so an assertion that it never reaches a
#: message cannot pass by coincidence.
LEAKED_VALUE = "sk-live-do-not-log-me-9f3a"

FIXTURE_REGISTRY = MappingProxyType(
    {
        "fixture_thing_created": RegisteredAction(
            action="fixture_thing_created",
            target_type="fixture_thing",
            detail_keys=frozenset({"alpha", "beta"}),
            requires_reason=False,
            writing_module="release-control",
        ),
        "fixture_thing_reasoned": RegisteredAction(
            action="fixture_thing_reasoned",
            target_type="fixture_thing",
            detail_keys=frozenset(),
            requires_reason=True,
            writing_module="release-control",
        ),
    }
)


def draft(**overrides) -> HistoryEventDraft:
    values = {
        "workspace_id": WORKSPACE_A,
        "actor_type": ActorType.USER,
        "actor_id": ACTOR_ID,
        "action": "fixture_thing_created",
        "target_type": "fixture_thing",
        "target_id": TARGET_ID,
        "occurred_at": day(5),
    }
    values.update(overrides)
    return HistoryEventDraft(**values)


def rejected_total(reason: str) -> float:
    """A DELTA source, never an absolute.

    ``prometheus_client``'s default registry is process-global and survives every
    test in the session, and a labelled counter has no sample at all until its
    first increment — which is why ``or 0.0`` is not defensive noise.
    """
    value = REGISTRY.get_sample_value(
        "prope_property_history_append_rejected_total", {"reason": reason}
    )
    return value or 0.0


def test_an_unregistered_action_is_refused():
    before = rejected_total("unknown_action")

    with pytest.raises(HistoryAppendRejected) as excinfo:
        check_event(draft(action="fixture_thing_invented"), FIXTURE_REGISTRY)

    assert excinfo.value.reason is RejectionReason.UNKNOWN_ACTION
    assert rejected_total("unknown_action") == before + 1


def test_a_details_key_outside_the_allow_list_is_refused():
    before = rejected_total("unknown_detail_key")

    with pytest.raises(HistoryAppendRejected) as excinfo:
        check_event(draft(details={"gamma": "x"}), FIXTURE_REGISTRY)

    assert excinfo.value.reason is RejectionReason.UNKNOWN_DETAIL_KEY
    assert excinfo.value.detail_key == "gamma"
    assert rejected_total("unknown_detail_key") == before + 1


def test_every_key_inside_the_allow_list_passes():
    check_event(draft(details={"alpha": 1, "beta": 2}), FIXTURE_REGISTRY)


def test_an_empty_details_payload_passes_an_action_that_declares_keys():
    """A subset, not an equality: declared keys are permitted, never required."""
    check_event(draft(details={}), FIXTURE_REGISTRY)


def test_a_missing_reason_is_refused_where_the_registry_requires_one():
    before = rejected_total("missing_reason")

    with pytest.raises(HistoryAppendRejected) as excinfo:
        check_event(draft(action="fixture_thing_reasoned"), FIXTURE_REGISTRY)

    assert excinfo.value.reason is RejectionReason.MISSING_REASON
    assert rejected_total("missing_reason") == before + 1


def test_a_whitespace_only_reason_is_refused():
    """It satisfies NOT NULL and the 500-character CHECK and is not a reason."""
    with pytest.raises(HistoryAppendRejected) as excinfo:
        check_event(draft(action="fixture_thing_reasoned", reason="   "), FIXTURE_REGISTRY)

    assert excinfo.value.reason is RejectionReason.MISSING_REASON


def test_a_reason_on_an_action_that_does_not_require_one_passes():
    """``requires_reason`` is a floor, not an exclusion."""
    check_event(draft(reason="ghi chú"), FIXTURE_REGISTRY)


def test_an_earlier_check_wins_when_a_draft_fails_two():
    """T-022 outranks a policy omission, so the payload leak is reported."""
    with pytest.raises(HistoryAppendRejected) as excinfo:
        check_event(
            draft(action="fixture_thing_reasoned", details={"gamma": "x"}),
            FIXTURE_REGISTRY,
        )

    assert excinfo.value.reason is RejectionReason.UNKNOWN_DETAIL_KEY


def test_the_refusal_message_names_the_key_and_never_the_value():
    with pytest.raises(HistoryAppendRejected) as excinfo:
        check_event(draft(details={"gamma": LEAKED_VALUE}), FIXTURE_REGISTRY)

    message = str(excinfo.value)
    assert "gamma" in message
    assert LEAKED_VALUE not in message


def test_a_nested_payload_under_a_registered_key_is_not_refused():
    """The recorded boundary: A-124's allow-list is over KEYS, and values are unchecked.

    ``check_event`` computes a top-level key-set difference, so
    ``details={"alpha": <whole response object>}`` — the shape A-124's own
    rationale names, *"just put the whole object in for debugging"* — passes. The
    key half is enforced; the value half is not, and ``prope_report`` holds
    ``SELECT`` on this column across every workspace.

    **If this test starts failing, do not "fix" it.** It failing means somebody
    added the value check, which is a real improvement — delete this test and the
    sentence recording the absence in
    ``src/prope/property_history/append.py``'s ``check_event`` docstring in the
    same change.
    """
    check_event(draft(details={"alpha": {"prompt_body": LEAKED_VALUE}}), FIXTURE_REGISTRY)


def test_rejection_reason_has_exactly_the_three_declared_label_values():
    """A fourth reason is a lock-file change, not a new enum member (D-63).

    The lock's ``PropertyHistoryAppendRejected`` alert pages on every increment,
    so a silently added fourth label value is a new page nobody declared.
    """
    assert {reason.value for reason in RejectionReason} == {
        "unknown_action",
        "unknown_detail_key",
        "missing_reason",
    }

"""The caller-supplied conversation id, from the request body to the draft.

Three boundaries carry the same rule and none of them may import the others'
copy of it: `gateway.schemas` gates the HTTP request, `call_ledger.envelope`
gates the broker message, and `prompt_registry.schemas` gates the URL path
segment. call-ledger may not import gateway, and prompt-registry may not import
gateway either — so the pattern is written out three times, and the first test
here is what stops the three from drifting apart in silence.

No database, no HTTP, no container. These are shapes and refusals.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from prope.call_ledger.domain import CallRecordDraft, Outcome, Source
from prope.call_ledger.envelope import CallRecordEnvelope, CallRecordPayload
from prope.gateway.schemas import (
    CHATCMPL_PREFIX,
    CONVERSATION_ID_MAX_LENGTH,
    CONVERSATION_ID_PATTERN,
    ChatCompletionRequest,
)
from prope.prompt_registry import schemas as registry_schemas

CALL_ID = "cal_01J0000000000000000000000A"
WHEN = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _request(**prope: object) -> ChatCompletionRequest:
    return ChatCompletionRequest.model_validate(
        {"model": "support/reply", "messages": [{"role": "user", "content": "hi"}], "prope": prope}
    )


def _draft(**kwargs: object) -> CallRecordDraft:
    return CallRecordDraft(
        call_id=CALL_ID,
        workspace_id="wsp_1",
        source=Source.GATEWAY,
        outcome=Outcome.OK,
        created_at=WHEN,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# The three copies of the rule
# ---------------------------------------------------------------------------


def test_the_three_boundaries_gate_the_id_identically() -> None:
    """One rule, written three times because no module may import another's copy.

    The character class is what keeps a slash out of a URL path segment and a
    control character out of an index key. If the gateway accepted something the
    route's path parameter refuses, a call would be recorded under an id that
    could never be read back — a conversation stored and permanently unreachable.
    """
    assert registry_schemas.CONVERSATION_ID_PATTERN == CONVERSATION_ID_PATTERN
    field = CallRecordPayload.model_fields["conversation_id"]
    patterns = [meta.pattern for meta in field.metadata if hasattr(meta, "pattern")]
    assert patterns == [CONVERSATION_ID_PATTERN]


@pytest.mark.parametrize(
    "value",
    ["with space", "has/slash", "quote'd", "new\nline", "", "x" * (CONVERSATION_ID_MAX_LENGTH + 1)],
)
def test_a_conversation_id_that_could_not_survive_a_url_is_refused(value: str) -> None:
    with pytest.raises(ValidationError):
        _request(conversation_id=value)


@pytest.mark.parametrize("value", ["conv-9f2", "chat_001", "01J8XYZ", "a", "x" * 64])
def test_the_shapes_a_real_application_generates_are_accepted(value: str) -> None:
    """UUIDs with hyphens, ULIDs, snake_case counters — all ordinary here."""
    assert _request(conversation_id=value).conversation_id() == value


# ---------------------------------------------------------------------------
# The parent, and the lenience that keeps the obvious integration working
# ---------------------------------------------------------------------------


def test_the_response_id_can_be_pasted_straight_back_as_the_parent() -> None:
    """The gateway answers `chatcmpl-cal_...`; that string must work as a parent.

    This is the whole reason the validator strips a prefix. The failure it
    prevents is silent — an unmatched parent is not an error, it is a node that
    renders as a second root — so an integration that looked correct would draw a
    broken chain and never say why.
    """
    request = _request(conversation_id="conv-1", parent_call_id=f"{CHATCMPL_PREFIX}{CALL_ID}")
    assert request.parent_call_id() == CALL_ID


def test_the_bare_call_id_works_too() -> None:
    assert _request(conversation_id="conv-1", parent_call_id=CALL_ID).parent_call_id() == CALL_ID


def test_a_conversation_id_put_in_the_parent_field_is_refused_rather_than_ignored() -> None:
    """The mistake the lenience above would otherwise hide.

    Having taught the field to accept two spellings of a call id, it has to be
    strict about everything else — otherwise the commonest confusion (*which id
    goes in which field?*) fails exactly as silently as the one being fixed.
    """
    with pytest.raises(ValidationError):
        _request(conversation_id="conv-1", parent_call_id="conv-1")


def test_a_parent_without_a_conversation_is_dropped_rather_than_stored() -> None:
    """A parent link with nothing to hang it in would be written and never read.

    The graph is assembled by conversation. Dropping it at the edge is what keeps
    the draft's own refusal from ever having to fire on a live gateway call.
    """
    request = _request(parent_call_id=CALL_ID)
    assert request.parent_call_id() is None


def test_a_request_that_says_nothing_about_conversations_still_works() -> None:
    """Every caller until they change one line. It must cost them nothing."""
    plain = ChatCompletionRequest.model_validate(
        {"model": "support/reply", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert plain.conversation_id() is None
    assert plain.parent_call_id() is None


def test_an_unknown_prope_option_is_still_refused() -> None:
    """`extra="forbid"` is what makes a typo visible instead of inert."""
    with pytest.raises(ValidationError):
        _request(conversationId="conv-1")


# ---------------------------------------------------------------------------
# The draft's own two refusals
# ---------------------------------------------------------------------------


def test_a_draft_with_a_parent_and_no_conversation_is_refused() -> None:
    with pytest.raises(ValueError, match="names a parent but no conversation"):
        _draft(parent_call_id="cal_other")


def test_a_draft_that_is_its_own_parent_is_refused() -> None:
    """A loop is not a chain, and a renderer given one may not terminate."""
    with pytest.raises(ValueError, match="its own parent"):
        _draft(conversation_id="conv-1", parent_call_id=CALL_ID)


def test_a_draft_may_name_a_parent_that_no_longer_exists() -> None:
    """Not a foreign key, deliberately.

    A parent can age out of retention while its child survives. Refusing that
    would mean the ledger could not record a call whose predecessor had expired —
    and the honest rendering of it is a root, not an error.
    """
    draft = _draft(conversation_id="conv-1", parent_call_id="cal_long_gone")
    assert draft.parent_call_id == "cal_long_gone"


# ---------------------------------------------------------------------------
# The broker wire
# ---------------------------------------------------------------------------


def test_the_envelope_carries_both_fields_into_the_draft() -> None:
    envelope = CallRecordEnvelope(
        schema_version=1,
        call_id=CALL_ID,
        workspace_id="wsp_prope",
        occurred_at=WHEN,
        producer="gateway",
        payload=CallRecordPayload(
            source=Source.GATEWAY,
            outcome=Outcome.OK,
            created_at=WHEN,
            conversation_id="conv-1",
            parent_call_id="cal_parent",
        ),
    )
    draft = envelope.to_draft()
    assert (draft.conversation_id, draft.parent_call_id) == ("conv-1", "cal_parent")


def test_an_envelope_whose_publisher_broke_the_rule_raises_rather_than_writing() -> None:
    """It dead-letters, which is where a publisher bug belongs.

    Loud, one message at a time, envelope preserved — rather than a CHECK
    constraint aborting the whole batch the writer is committing and taking a
    hundred innocent records down with one malformed one.
    """
    envelope = CallRecordEnvelope(
        schema_version=1,
        call_id=CALL_ID,
        workspace_id="wsp_prope",
        occurred_at=WHEN,
        producer="gateway",
        payload=CallRecordPayload(
            source=Source.GATEWAY,
            outcome=Outcome.OK,
            created_at=WHEN,
            parent_call_id="cal_parent",
        ),
    )
    with pytest.raises(ValueError, match="names a parent but no conversation"):
        envelope.to_draft()


def test_the_publisher_puts_both_fields_on_the_wire() -> None:
    """The half the test above did not cover, and where the bug actually was.

    `from_draft` omitted `conversation_id` and `parent_call_id`, so a gateway
    call that named a conversation published an envelope that did not. Nothing
    refused it: the fields are optional, `to_draft` read back the `None` the
    publisher never set, and the writer committed a row with a null
    conversation. Every graph came out empty, in production, silently.

    Building the envelope by hand — which is what the test above does — cannot
    catch that, and `from_draft`'s own docstring says why: a publisher that built
    the envelope by hand would be a second place the wire contract is written
    down. So this one goes through the publisher.
    """
    draft = _draft(conversation_id="conv-1", parent_call_id="cal_parent")

    envelope = CallRecordEnvelope.from_draft(draft, occurred_at=WHEN)

    assert (envelope.payload.conversation_id, envelope.payload.parent_call_id) == (
        "conv-1",
        "cal_parent",
    )


#: Carried on ``CallBodyDraft`` rather than on the draft itself, so the generic
#: sweep below cannot compare them by name.
BODY_FIELDS = frozenset({"request_body", "response_body", "byte_size"})


def test_every_payload_field_survives_the_round_trip() -> None:
    """Field-driven, so the next field added to the wire is covered by writing it.

    The defect this replaces was one line missing from a list of twenty-three
    assignments, in a method whose failure is silent by construction: every
    field is optional, so an omission publishes successfully, validates
    successfully, and writes a null. Naming each field in a test would have the
    same hole — the test would be the same list, and the same line would be
    missing from it.
    """
    values: dict[str, object] = {
        "prompt_id": "prm_1",
        "version_id": "rev_1",
        "revision_number": 7,
        "run_id": "run_1",
        "case_id": "cas_1",
        "conversation_id": "conv-1",
        "parent_call_id": "cal_parent",
        "consumer_key_id": "key_1",
        "actor_id": "usr_1",
        "provider_config_id": "prv_1",
        "upstream_model": "gpt-4o-mini",
        "pinned": True,
        "fallback": True,
        "streaming": True,
        "input_tokens": 11,
        "output_tokens": 13,
        "added_latency_ms": 17,
        "upstream_duration_ms": 19,
        "error_class": "upstream_timeout",
    }
    always_set = {"source", "outcome", "created_at"}
    missing = [
        name
        for name in CallRecordPayload.model_fields
        if name not in BODY_FIELDS and name not in always_set and name not in values
    ]
    assert not missing, f"no value chosen for {missing}; add one so the field is actually exercised"

    draft = _draft(**values)
    back = CallRecordEnvelope.from_draft(draft, occurred_at=WHEN).to_draft()

    for name, expected in values.items():
        assert getattr(back, name) == expected, f"{name} was lost between the draft and the wire"

"""The request shape and the answer shape, with no transport in the way.

These are the tests that would catch a change to what Prope is *sent*, which is
the thing a customer's application depends on and the thing that cannot be
fixed by redeploying Prope.
"""

from __future__ import annotations

import pytest

from prope_sdk import _wire
from prope_sdk.errors import (
    AuthenticationError,
    CallerSystemMessage,
    InvalidRequest,
    MissingVariable,
    ModelNotFound,
    PropeError,
    RateLimited,
    UpstreamError,
)

USER = [{"role": "user", "content": "Where is my refund?"}]


# --- the request ------------------------------------------------------------


def test_a_plain_call_carries_no_prope_block_at_all() -> None:
    """An empty block is omitted rather than sent as `{}`.

    A request with no Prope-specific intent has to look on the wire exactly like
    one from a plain OpenAI client — that is what makes the gateway's two
    consumers one contract rather than two.
    """
    body = _wire.build_body(prompt="support/x", messages=USER)

    assert body == {"model": "support/x", "messages": USER, "stream": False}
    assert "prope" not in body


def test_the_pin_goes_in_the_model_string_and_not_the_prope_block() -> None:
    body = _wire.build_body(prompt="support/x", messages=USER, pin="v3")

    assert body["model"] == "support/x@v3"
    assert "prope" not in body


def test_an_empty_pin_is_the_same_as_no_pin() -> None:
    """A pin read from a config file that happens to be blank must not address
    `support/x@` — a name that resolves to nothing and refuses identically to a
    prompt the key cannot see."""
    assert _wire.model_reference("support/x", "") == "support/x"
    assert _wire.model_reference("support/x", "   ") == "support/x"


def test_a_parent_without_a_conversation_is_dropped() -> None:
    """The gateway drops it too — a parent with nothing to hang it in is stored
    and never read — so dropping it here keeps the request identical to what
    will be recorded."""
    body = _wire.build_body(prompt="support/x", messages=USER, parent_call_id="call_1")

    assert "prope" not in body


def test_a_parent_with_a_conversation_is_kept() -> None:
    body = _wire.build_body(
        prompt="support/x", messages=USER, conversation_id="conv_1", parent_call_id="call_1"
    )

    assert body["prope"] == {"conversation_id": "conv_1", "parent_call_id": "call_1"}


def test_provider_parameters_pass_through_but_cannot_overwrite_prope_fields() -> None:
    """`temperature` is the caller's business. `model` is not.

    A caller passing `model=` as a keyword would otherwise silently address a
    different prompt than the one named in the first argument, which is the
    quietest possible way to call the wrong revision.
    """
    body = _wire.build_body(
        prompt="support/x",
        messages=USER,
        extra={"temperature": 0.2, "model": "gpt-4o-mini", "messages": [], "prope": {"variables": {}}},
    )

    assert body["temperature"] == 0.2
    assert body["model"] == "support/x"
    assert body["messages"] == USER
    assert "prope" not in body


def test_streaming_asks_for_usage() -> None:
    body = _wire.build_body(prompt="support/x", messages=USER, stream=True)

    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}


def test_a_caller_system_message_is_refused_locally_and_names_its_index() -> None:
    """The most likely mistake in a freshly migrated call site: the literal that
    used to be the system prompt is still being passed next to the model name
    that now carries it."""
    messages = [{"role": "system", "content": "You are a helpful assistant."}, *USER]

    with pytest.raises(CallerSystemMessage) as raised:
        _wire.check_messages(messages)

    assert raised.value.param == "messages.0.role"
    assert "system" in str(raised.value)


def test_assistant_and_tool_roles_are_fine() -> None:
    _wire.check_messages(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "tool", "content": "{}", "tool_call_id": "t1"},
        ]
    )


# --- refusals ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (401, "authentication_failed", AuthenticationError),
        (404, "model_not_found", ModelNotFound),
        (429, "rate_limit_exceeded", RateLimited),
        (400, "missing_variable", MissingVariable),
        (400, "system_message_not_allowed", CallerSystemMessage),
        (400, "request_too_large", InvalidRequest),
        (500, "provider_configuration_unusable", UpstreamError),
        (502, "upstream_error", UpstreamError),
    ],
)
def test_each_refusal_maps_to_the_narrowest_honest_exception(
    status: int, code: str, expected: type[Exception]
) -> None:
    payload = {"error": {"message": "no", "code": code, "type": "invalid_request_error"}}

    with pytest.raises(expected) as raised:
        _wire.raise_for(status, payload)

    assert raised.value.code == code  # type: ignore[attr-defined]
    assert raised.value.status == status  # type: ignore[attr-defined]


def test_a_body_prope_did_not_write_still_raises_something_useful() -> None:
    """A load balancer's HTML page or an empty 502 has no `error` object. It must
    not surface as an exception whose message is `None`."""
    with pytest.raises(UpstreamError) as raised:
        _wire.raise_for(502, None)

    assert "502" in str(raised.value)
    assert raised.value.code is None


def test_missing_variable_names_the_variable() -> None:
    payload = {"error": {"message": "needs it", "code": "missing_variable", "param": "prope.variables.tier"}}

    with pytest.raises(MissingVariable) as raised:
        _wire.raise_for(400, payload)

    assert raised.value.name == "tier"


def test_rate_limited_carries_retry_after_when_the_gateway_sent_one() -> None:
    with pytest.raises(RateLimited) as raised:
        _wire.raise_for(429, {"error": {"message": "slow down"}}, {"retry-after": "1"})

    assert raised.value.retry_after == 1.0


def test_a_success_raises_nothing() -> None:
    _wire.raise_for(200, {"choices": []})


def test_an_unmapped_client_error_is_still_a_prope_error() -> None:
    with pytest.raises(PropeError):
        _wire.raise_for(418, {"error": {"message": "teapot"}})


# --- the answer -------------------------------------------------------------


COMPLETION = {
    "id": "cmpl-1",
    "model": "support/refund-classifier",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
    "prope": {
        "version_id": "ver_1",
        "revision_number": 2,
        "pinned": False,
        "fallback": False,
        "upstream_model": "gpt-4o-mini",
    },
}


def test_the_answer_carries_the_identity_of_what_served_it() -> None:
    answer = _wire.answer_from(COMPLETION, {"x-prope-call-id": "call_9"})

    assert answer.text == "pong"
    assert answer.model == "support/refund-classifier"
    assert answer.version_id == "ver_1"
    assert answer.revision == 2
    assert answer.upstream_model == "gpt-4o-mini"
    assert answer.call_id == "call_9"
    assert answer.usage.total_tokens == 4


def test_the_call_id_comes_from_the_header_because_the_body_has_none() -> None:
    """It is what the next step of a chain sends as `parent_call_id`, so a
    client that read only the body would leave every step a root."""
    answer = _wire.answer_from(COMPLETION, {"X-Prope-Call-Id": "call_9"})

    assert answer.call_id == "call_9"


def test_headers_fill_in_only_what_the_body_lacks() -> None:
    thin = {"model": "support/x", "choices": []}
    answer = _wire.answer_from(
        thin,
        {
            "x-prope-version-id": "ver_7",
            "x-prope-revision": "5",
            "x-prope-pinned": "true",
            "x-prope-fallback": "true",
            "x-prope-call-id": "call_2",
        },
    )

    assert (answer.version_id, answer.revision) == ("ver_7", 5)
    assert answer.pinned and answer.fallback


def test_an_answer_never_carries_a_prompt_body() -> None:
    """ADR-0065, asserted rather than assumed. If a future response ever included
    the revision body, `Answer` must still not surface it as a field somebody
    can reach for."""
    answer = _wire.answer_from(COMPLETION, {})

    assert not hasattr(answer, "body")
    assert not hasattr(answer, "prompt")
    assert not hasattr(answer, "system_prompt")


# --- streaming --------------------------------------------------------------


def test_sse_parsing_skips_done_blanks_and_junk() -> None:
    lines = iter(
        [
            "",
            ": keep-alive",
            'data: {"choices":[{"delta":{"content":"he"}}]}',
            "data: not json at all",
            'data: {"choices":[{"delta":{"content":"llo"}}]}',
            "data: [DONE]",
        ]
    )

    text = "".join(_wire.chunk_from(payload).text for payload in _wire.sse_payloads(lines))

    assert text == "hello"


def test_a_chunk_carrying_only_usage_yields_empty_text_rather_than_failing() -> None:
    """So a caller can concatenate every chunk's text without filtering."""
    chunk = _wire.chunk_from({"choices": [], "usage": {"total_tokens": 9}})

    assert chunk.text == ""
    assert chunk.usage is not None and chunk.usage.total_tokens == 9


def test_a_mid_stream_error_frame_raises() -> None:
    """The gateway relays an upstream failure as its own event and records the
    call as truncated. Continuing would build a string with no reason to be
    trusted."""
    with pytest.raises(UpstreamError):
        _wire.chunk_from({"error": {"message": "upstream died", "code": "upstream_error"}})

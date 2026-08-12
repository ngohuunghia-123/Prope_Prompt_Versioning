"""AC-4 — the caller has no parameter that can turn usage reporting off (A-089)."""

import pytest

from prope.provider_access import upstream
from prope.provider_access.normalise import read_usage
from tests.provider_access import _stub

MESSAGES = ({"role": "user", "content": "hello"},)


def test_a_streaming_request_asks_for_usage_when_the_caller_said_nothing() -> None:
    payload = upstream.compose_request(
        upstream_model="gpt-4o-mini", parameters={}, messages=MESSAGES, stream=True
    )

    assert payload["stream_options"] == {"include_usage": True}


def test_a_caller_cannot_turn_usage_off_by_sending_stream_options() -> None:
    """The parameter is not merged, it is replaced: a revision carrying
    `stream_options: {include_usage: false}` would otherwise make its own calls
    unpriceable, silently, and the hole would show up as a gap in a cost metric
    months later."""
    payload = upstream.compose_request(
        upstream_model="gpt-4o-mini",
        parameters={"stream_options": {"include_usage": False}, "temperature": 0.2},
        messages=MESSAGES,
        stream=True,
    )

    assert payload["stream_options"] == {"include_usage": True}
    assert payload["temperature"] == 0.2


def test_a_caller_cannot_override_the_model_the_messages_or_the_stream_flag() -> None:
    """A-024: the revision carries the binding and the caller cannot override it."""
    payload = upstream.compose_request(
        upstream_model="gpt-4o-mini",
        parameters={"model": "gpt-4o", "messages": [], "stream": True},
        messages=MESSAGES,
        stream=False,
    )

    assert payload["model"] == "gpt-4o-mini"
    assert payload["messages"] == [dict(message) for message in MESSAGES]
    assert payload["stream"] is False


def test_generation_parameters_pass_through_verbatim() -> None:
    """A-097 — a parameter the provider rejects is a revision defect, not
    something this module repairs on the way past."""
    payload = upstream.compose_request(
        upstream_model="gpt-4o-mini",
        parameters={"temperature": 2.5, "response_format": {"type": "json_object"}, "top_p": 0.1},
        messages=MESSAGES,
        stream=False,
    )

    assert payload["temperature"] == 2.5
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["top_p"] == 0.1


async def test_the_request_that_actually_leaves_carries_the_usage_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asserted on the composed HTTP request rather than on the dict, because
    the dict is not what the provider sees."""
    payload = upstream.compose_request(
        upstream_model="gpt-4o-mini",
        parameters={"stream_options": {"include_usage": False}},
        messages=MESSAGES,
        stream=True,
    )

    with _stub.stub_provider(
        monkeypatch, lambda request: _stub.httpx.Response(200, json=_stub.completion())
    ) as recorder:
        await upstream.call_json(
            _stub.endpoint(),
            "sk-test-secret",
            path=upstream.CHAT_COMPLETIONS_PATH,
            payload=payload,
            timeout_seconds=5.0,
        )

    assert recorder.body()["stream_options"] == {"include_usage": True}


def test_the_usage_parser_reads_both_field_spellings() -> None:
    """The ±2% success metric is a parse, so both the OpenAI names and the
    input/output pair a compatible endpoint may use are read."""
    openai_shaped = read_usage(
        {"usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16}}
    )
    alternative = read_usage({"usage": {"input_tokens": 11, "output_tokens": 5}})

    assert (openai_shaped.input_tokens, openai_shaped.output_tokens) == (11, 5)
    assert (alternative.input_tokens, alternative.output_tokens) == (11, 5)
    assert alternative.total_tokens == 16


def test_a_response_with_no_usage_object_parses_as_none_and_never_as_zero() -> None:
    """ADR-0019's rule at this seam: a zero standing in for an absent count is
    a cost figure nobody can tell from a free call."""
    assert read_usage({"choices": []}) is None
    assert read_usage({"usage": {}}) is None

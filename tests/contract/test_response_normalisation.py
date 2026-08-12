"""AC-9 — parsed with a real OpenAI SDK model, never by hand-checking keys.

A near-miss survives hand-built assertions and then breaks every consumer, which
is why the oracle is the SDK's own model. The SDK is a TEST-ONLY dependency: it
is deliberately not the client, because A-088's exactly-one-attempt, this file's
unknown-field pass-through, and ADR-0047's address pinning each rule it out.
"""

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from prope.provider_access.normalise import (
    CHUNK_OBJECT,
    COMPLETION_OBJECT,
    normalise_chunk,
    normalise_response,
)

MODEL = "gpt-4o-mini"

OPENAI_SHAPED = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1_760_000_000,
    "model": MODEL,
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hello"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11},
}

#: What "OpenAI-compatible" turns out to mean in practice: the happy path is the
#: same shape and the edges are not. No `object`, no `created`, no `index`, no
#: `finish_reason`, and the usage object under the other pair of names.
NEARLY_SHAPED = {
    "id": "resp-77",
    "choices": [{"message": {"role": "assistant", "content": "hello"}}],
    "usage": {"input_tokens": 9, "output_tokens": 2},
}


def test_a_compatible_response_parses_as_a_real_chat_completion() -> None:
    normalised = normalise_response(OPENAI_SHAPED, model=MODEL)

    parsed = ChatCompletion.model_validate(normalised)

    assert parsed.object == COMPLETION_OBJECT
    assert parsed.choices[0].message.content == "hello"
    assert parsed.usage.prompt_tokens == 9


def test_a_nearly_compatible_response_is_repaired_into_the_same_object() -> None:
    """The `adapter` column and this boundary are what make a second adapter
    additive rather than a rewrite (A-094, ADR-0015)."""
    normalised = normalise_response(NEARLY_SHAPED, model=MODEL)

    parsed = ChatCompletion.model_validate(normalised)

    assert parsed.object == COMPLETION_OBJECT
    assert parsed.model == MODEL
    assert parsed.choices[0].index == 0
    assert parsed.usage.prompt_tokens == 9
    assert parsed.usage.completion_tokens == 2
    assert parsed.usage.total_tokens == 11


def test_a_field_prope_does_not_model_is_present_unchanged() -> None:
    """The second half of AC-9. A provider's own extension is the caller's to
    read, and dropping it would make Prope a lossy proxy for its own consumers."""
    with_extras = {
        **OPENAI_SHAPED,
        "system_fingerprint": "fp_44709d6fcb",
        "prompt_logprobs": None,
        "x_provider_trace": {"region": "eu-west-1", "shard": 3},
    }

    normalised = normalise_response(with_extras, model=MODEL)

    assert normalised["x_provider_trace"] == {"region": "eu-west-1", "shard": 3}
    assert normalised["system_fingerprint"] == "fp_44709d6fcb"
    assert ChatCompletion.model_validate(normalised).system_fingerprint == "fp_44709d6fcb"


def test_an_unknown_field_inside_a_choice_survives_too() -> None:
    """A pass-through that only worked at the top level would drop exactly the
    fields a provider adds — they arrive inside the choice."""
    nested = {
        **OPENAI_SHAPED,
        "choices": [{**OPENAI_SHAPED["choices"][0], "x_confidence": 0.91}],
    }

    normalised = normalise_response(nested, model=MODEL)

    assert normalised["choices"][0]["x_confidence"] == 0.91


def test_a_stream_chunk_parses_as_a_real_chunk() -> None:
    chunk = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1_760_000_000,
        "model": MODEL,
        "choices": [{"index": 0, "delta": {"content": "he"}, "finish_reason": None}],
    }

    parsed = ChatCompletionChunk.model_validate(normalise_chunk(chunk, model=MODEL))

    assert parsed.object == CHUNK_OBJECT
    assert parsed.choices[0].delta.content == "he"


def test_a_chunk_carrying_a_message_instead_of_a_delta_is_repaired() -> None:
    """The commonest streaming divergence among compatible endpoints, and the
    one that makes a client render nothing at all rather than fail."""
    chunk = {"id": "c", "choices": [{"message": {"content": "he"}}]}

    parsed = ChatCompletionChunk.model_validate(normalise_chunk(chunk, model=MODEL))

    assert parsed.choices[0].delta.content == "he"


def test_the_final_usage_chunk_parses_and_keeps_its_counts() -> None:
    """`stream_options.include_usage` puts usage on a chunk with no choices,
    and that chunk is the whole of the ±2% metric on a streamed call."""
    chunk = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1_760_000_000,
        "model": MODEL,
        "choices": [],
        "usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11},
    }

    parsed = ChatCompletionChunk.model_validate(normalise_chunk(chunk, model=MODEL))

    assert parsed.usage.total_tokens == 11

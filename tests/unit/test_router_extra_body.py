"""The router's vendor parameters: a latency control that must not leak.

`CHAT_ROUTER_EXTRA_BODY` is the one place Prope sends provider-specific JSON to
the gateway, and the property that makes that safe is narrow: **silence must
mean silence**. A deployment that sets nothing must produce a request identical
to the one it produced before this setting existed, because every spelling this
knob has carried is refused or ignored by some provider — OpenRouter answers
HTTP 400 to `{"reasoning": {"enabled": false}}`, and silently ignores Gemini's
`thinking_config`.

So the tests are about the *absence* as much as the presence: unset sends no
key, unparsable JSON sends no key, JSON that is not an object sends no key, and
an operator who wrote a valid object gets exactly that object — unrewritten,
because this module deliberately does not know what the parameters mean.

Nothing here calls a model.
"""

import importlib
import inspect
import os

import pytest

from prope.app_agent import dspy_runtime
from prope.chat_orchestrator import dspy_program


def _reloaded(monkeypatch: pytest.MonkeyPatch, value: str | None):
    """`dspy_program` with one environment variable set, re-read at import.

    The module resolves its settings into `Final` constants at import time, the
    same as every other tuning value in it, so a test that only sets the
    environment would assert against the value the test session happened to
    start with.
    """
    if value is None:
        monkeypatch.delenv("CHAT_ROUTER_EXTRA_BODY", raising=False)
    else:
        monkeypatch.setenv("CHAT_ROUTER_EXTRA_BODY", value)
    return importlib.reload(dspy_program)


@pytest.fixture(autouse=True)
def _restore_module():
    """Leave the imported module as this session found it.

    `importlib.reload` rebinds the module object every other test in the run
    shares, and `dspy_program` holds the program caches. Reloading it back to
    the ambient environment at teardown keeps this file from changing what
    another file sees.
    """
    yield
    importlib.reload(dspy_program)


# ---------------------------------------------------------------------------
# Silence means silence
# ---------------------------------------------------------------------------


def test_unset_sends_no_vendor_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reloaded(monkeypatch, None)
    assert module.router_extra_body() is None


@pytest.mark.parametrize("value", ["", "   ", "not json", "{unquoted: 1}", "{", "0.5,"])
def test_json_that_will_not_parse_sends_nothing(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """A typo degrades to today's behaviour rather than to a 400 on every turn.

    The router runs ahead of everything else, and this is read at import, so a
    malformed tuning value that raised would take the whole assistant down over
    a setting whose only job is to make it faster.
    """
    module = _reloaded(monkeypatch, value)
    assert module.router_extra_body() is None


@pytest.mark.parametrize("value", ["[1, 2]", '"a string"', "128", "null", "true"])
def test_valid_json_that_is_not_an_object_sends_nothing(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """These parse and are still wrong: a request body fragment is a mapping.

    Caught here rather than at the provider, where the same mistake surfaces as
    a transport error several layers from the setting that caused it.
    """
    module = _reloaded(monkeypatch, value)
    assert module.router_extra_body() is None


# ---------------------------------------------------------------------------
# What an operator who asked for it gets
# ---------------------------------------------------------------------------


def test_the_object_is_forwarded_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unrewritten, and that is the whole design.

    The value measured on the currently configured gateway. This module must not
    know that `reasoning` means anything — the previous version of this setting
    hardcoded Gemini's `thinking_config`, which became a silent no-op the day
    the gateway moved to OpenRouter.
    """
    module = _reloaded(monkeypatch, '{"reasoning": {"max_tokens": 128}}')
    assert module.router_extra_body() == {"reasoning": {"max_tokens": 128}}


def test_a_different_provider_spelling_is_equally_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The spelling that worked on the gateway before this one."""
    module = _reloaded(monkeypatch, '{"google": {"thinking_config": {"thinking_budget": 0}}}')
    assert module.router_extra_body() == {"google": {"thinking_config": {"thinking_budget": 0}}}


def test_nesting_and_types_survive_the_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """No coercion: booleans stay booleans and nested objects stay nested."""
    module = _reloaded(monkeypatch, '{"a": {"b": [1, 2]}, "c": false, "d": null, "e": 1.5}')
    assert module.router_extra_body() == {"a": {"b": [1, 2]}, "c": False, "d": None, "e": 1.5}


def test_surrounding_whitespace_does_not_defeat_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `.env` line with a trailing space is still the object it looks like."""
    module = _reloaded(monkeypatch, '  {"reasoning": {"max_tokens": 128}}  ')
    assert module.router_extra_body() == {"reasoning": {"max_tokens": 128}}


# ---------------------------------------------------------------------------
# The seam into the shared LM builder
# ---------------------------------------------------------------------------


def test_build_lm_omits_extra_body_when_there_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not `extra_body=None` on the request — the key absent entirely."""
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(dspy_runtime.dspy, "LM", _capture)
    dspy_runtime.build_lm(max_tokens=100)

    assert "extra_body" not in captured


def test_build_lm_forwards_extra_body_when_given(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(dspy_runtime.dspy, "LM", _capture)
    body = {"google": {"thinking_config": {"thinking_budget": 0}}}
    dspy_runtime.build_lm(max_tokens=100, extra_body=body)

    assert captured["extra_body"] == body


def test_the_router_lm_carries_what_the_environment_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end through the builder the orchestrator actually calls."""
    module = _reloaded(monkeypatch, '{"reasoning": {"max_tokens": 128}}')
    captured: dict[str, object] = {}

    def _capture(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(dspy_runtime.dspy, "LM", _capture)
    module.build_router_lm()

    assert captured["extra_body"] == {"reasoning": {"max_tokens": 128}}
    # The rest of the router's LM contract is unchanged by this addition.
    assert captured["max_tokens"] == module.MAX_ROUTER_TOKENS
    assert captured["cache"] is False
    assert captured["temperature"] == 0.0


def test_the_reply_and_draft_programs_are_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """The budget is the router's alone.

    The responder writes prose and the drafter rewrites a whole prompt body;
    neither was measured, and a latency setting that quietly changed how a
    revision is drafted would be changing output somebody approves.
    """
    module = _reloaded(monkeypatch, '{"reasoning": {"max_tokens": 128}}')
    captured: list[dict[str, object]] = []

    def _capture(**kwargs: object) -> object:
        captured.append(dict(kwargs))
        return object()

    monkeypatch.setattr(dspy_runtime.dspy, "LM", _capture)
    module.build_reply_lm()
    module.build_draft_lm()

    assert all("extra_body" not in call for call in captured)


# ---------------------------------------------------------------------------
# Empty is not the same as unset
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "attribute", "expected"),
    [
        ("CHAT_ROUTER_MAX_OUTPUT_TOKENS", "MAX_ROUTER_TOKENS", 2048),
        ("CHAT_REPLY_MAX_OUTPUT_TOKENS", "MAX_REPLY_TOKENS", 3000),
        ("CHAT_DRAFT_MAX_OUTPUT_TOKENS", "MAX_DRAFT_TOKENS", 4000),
        ("CHAT_EVIDENCE_CHAR_LIMIT", "EVIDENCE_CHARACTER_LIMIT", 6000),
        ("CHAT_HISTORY_CHAR_LIMIT", "MAX_HISTORY_CHARACTERS", 1200),
        ("CHAT_THREAD_ENTITY_LIMIT", "MAX_THREAD_ENTITIES", 4),
        ("CHAT_ROUTER_NUM_RETRIES", "ROUTER_NUM_RETRIES", 1),
        ("CHAT_ROUTER_TIMEOUT_SECONDS", "ROUTER_TIMEOUT_SECONDS", 30),
    ],
)
def test_a_forwarded_but_unset_setting_falls_back_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, name: str, attribute: str, expected: float
) -> None:
    """`${VAR:-}` in compose sets the empty string, and `int("")` raises.

    Every setting here is read at import, so before `_setting` existed one
    forwarded-but-unset tuning variable would have raised `ValueError` while the
    app was still importing — the container never starting, over a knob nobody
    turned. `docker-compose.yml` now forwards all sixteen this way so the
    default lives in one place; this is the test that keeps that safe.
    """
    monkeypatch.setenv(name, "")
    module = importlib.reload(dspy_program)

    assert getattr(module, attribute) == expected


def test_whitespace_is_treated_as_unset_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `.env` line written as `CHAT_ROUTER_TIMEOUT_SECONDS= ` is still unset."""
    monkeypatch.setenv("CHAT_ROUTER_TIMEOUT_SECONDS", "   ")
    module = importlib.reload(dspy_program)

    assert module.ROUTER_TIMEOUT_SECONDS == 30


def test_the_warmup_ping_stays_on_when_the_variable_is_forwarded_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Off is a legitimate setting; arriving there invisibly is not.

    The check reads `!= "1"`, so an empty forwarded value would have inverted
    the default and turned the deploy-time warm-up off everywhere — silently,
    and visible only as the first person of every deploy waiting ~10s.
    """
    from prope.chat_orchestrator import orchestrator

    source = inspect.getsource(orchestrator.warm_chat_agent)
    assert 'os.environ.get("CHAT_WARMUP_PING", "").strip() or "1"' in source

    monkeypatch.setenv("CHAT_WARMUP_PING", "")
    assert (os.environ.get("CHAT_WARMUP_PING", "").strip() or "1") == "1"

    monkeypatch.setenv("CHAT_WARMUP_PING", "0")
    assert (os.environ.get("CHAT_WARMUP_PING", "").strip() or "1") != "1"

"""`prope.version` — the request-body spelling of A-022's pin.

The field exists because a typed SDK holds the model name in configuration and
the version in the call, and assembling `f"{model}@{version}"` by hand is the
step an integrator forgets. What it must NOT become is a second resolution path:
everything here is about the value arriving normalised to the same text the `@`
form produces, so that one lookup, one cache key and one refusal shape serve both.

No database and no HTTP. These are shapes and refusals.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from prope.gateway.schemas import ChatCompletionRequest


def _request(**prope: Any) -> ChatCompletionRequest:
    return ChatCompletionRequest.model_validate(
        {"model": "support/reply", "messages": [{"role": "user", "content": "hi"}], "prope": prope}
    )


def test_a_number_arrives_as_the_text_a_pin_is_compared_as() -> None:
    """JSON has a number type and a revision number is a number, so `{"version": 2}`
    is what somebody writes first. It becomes `"2"` because one module over the
    pin is text that the registry decides how to compare."""
    assert _request(version=2).version() == "2"


def test_the_same_version_written_as_a_string_is_the_same_value() -> None:
    assert _request(version="2").version() == _request(version=2).version()


def test_a_version_id_is_carried_verbatim() -> None:
    assert _request(version="rev_01J000000000000000000REV1").version() == (
        "rev_01J000000000000000000REV1"
    )


def test_surrounding_space_is_not_a_different_revision() -> None:
    """A value read out of an environment variable or a config file arrives with
    whatever whitespace was around it, and `" 2"` matching no revision would be a
    404 nobody can see the cause of."""
    assert _request(version=" 2 ").version() == "2"


def test_no_prope_object_at_all_asks_for_no_version() -> None:
    """The request every existing consumer already sends."""
    payload = ChatCompletionRequest.model_validate(
        {"model": "support/reply", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert payload.version() is None


def test_a_prope_object_without_a_version_asks_for_no_version() -> None:
    """A caller using `variables` and nothing else keeps being served the
    released revision — which is the behaviour the product is sold on."""
    assert _request(variables={"tone": "formal"}).version() is None


def test_a_boolean_is_refused_rather_than_read_as_revision_one() -> None:
    """`bool` is an `int` subclass in Python, so `{"version": true}` would
    otherwise pin revision 1 — a wrong revision served silently, which is the one
    failure this field exists to prevent."""
    with pytest.raises(ValidationError):
        _request(version=True)


@pytest.mark.parametrize("value", ["", "   ", 1.5, {"n": 1}, [1], None.__class__])
def test_a_value_that_could_never_name_a_revision_is_refused_at_the_edge(value: Any) -> None:
    """Shape only. These are refused without the registry being consulted, so the
    refusal is identical whether the prompt exists, is invisible to this key, or
    was never created (A-116)."""
    with pytest.raises(ValidationError):
        _request(version=value)


def test_a_version_carrying_the_other_spellings_separator_is_refused() -> None:
    """`{"version": "support/reply@2"}` is somebody pasting the whole model
    reference into the field. Passing it through would produce a 404 whose cause
    is invisible; the 422 says which half belongs here."""
    with pytest.raises(ValidationError):
        _request(version="support/reply@2")


def test_an_explicit_null_is_the_same_as_omitting_it() -> None:
    """A client that always sends the key and leaves it empty when it does not
    care is an ordinary way to build a request body."""
    assert _request(version=None).version() is None


def test_a_misspelled_field_is_still_a_422_and_not_a_silent_no_op() -> None:
    """`extra="forbid"` on the options object, which is what the class was given
    it for: a typo in an integration must be visible rather than a feature that
    quietly never works."""
    with pytest.raises(ValidationError):
        _request(versions=2)

"""A-021 and A-022: `namespace/name`, `@<n>`, `@<version_id>`, and every malformed shape.

This is the first thing that touches a consumer's input on the one
internet-facing route, and the parse decides what reaches a database lookup. The
pin is kept OUT of :class:`ModelName` on purpose — `support/refund@3` is a name
and a pin, and merging them is how a pin reaches a unique-constraint lookup.
"""

import pytest

from prope.gateway.domain import (
    ModelReferenceConflict,
    ModelReferenceInvalid,
    parse_model_reference,
    pinned_at,
)

VERSION_ID = "rev_01J000000000000000000REV1"


def test_a_bare_name_carries_no_pin() -> None:
    reference = parse_model_reference("support/refund-classifier")

    assert reference.model_name == "support/refund-classifier"
    assert reference.pin is None
    assert reference.pinned is False


def test_a_numeric_pin_is_kept_beside_the_name_and_not_inside_it() -> None:
    reference = parse_model_reference("support/refund-classifier@7")

    assert reference.model_name == "support/refund-classifier"
    assert reference.pin == "7"
    assert reference.pinned is True


def test_a_version_id_pin_is_carried_verbatim() -> None:
    """`@<n>` and `@<version_id>` are different COLUMNS one module over, which is
    why the pin travels as text and the registry decides which to compare."""
    reference = parse_model_reference("support/refund-classifier@rev_01J000000000000000000REV1")

    assert reference.pin == "rev_01J000000000000000000REV1"


def test_the_raw_string_survives_for_the_response_and_the_refusal() -> None:
    """A-079 echoes the model field the caller asked for, and a not-found names
    it. Both need what was sent, not what it parsed to."""
    reference = parse_model_reference("support/refund-classifier@7")

    assert reference.raw == "support/refund-classifier@7"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "refund-classifier",
        "support/refund/classifier",
        "support/",
        "/refund-classifier",
        "Support/Refund",
        "support/refund classifier",
        "support/refund@",
        "support/refund@7@8",
        "support/-refund",
        "support/refund" + "x" * 64,
    ],
)
def test_every_malformed_shape_is_refused_rather_than_looked_up(raw: str) -> None:
    """A-021's shape, and the reason it is enforced here rather than in SQL: an
    unparseable name that reached the lookup would be a database round trip a
    stranger can provoke on the hot path, and `Support/Refund` would be a support
    conversation about case sensitivity nobody wins."""
    with pytest.raises(ModelReferenceInvalid):
        parse_model_reference(raw)


def test_a_refused_name_carries_what_was_sent_so_the_404_can_name_it() -> None:
    with pytest.raises(ModelReferenceInvalid) as raised:
        parse_model_reference("gpt-4o-mini")

    assert raised.value.raw == "gpt-4o-mini"


def test_dots_and_underscores_are_inside_the_shape() -> None:
    """`A-021`'s pattern allows them after the first character, and a prompt
    named `billing/invoice_v2.1` is an ordinary thing for a person to type."""
    reference = parse_model_reference("billing/invoice_v2.1")

    assert reference.model_name == "billing/invoice_v2.1"


# ---------------------------------------------------------------------------
# `prope.version` folded into the same reference — the second spelling of A-022
# ---------------------------------------------------------------------------


def test_a_body_version_pins_a_name_that_carried_none() -> None:
    """The whole point of the field: `{"model": "support/x", "prope": {"version": 2}}`
    must reach the registry as the identical lookup `support/x@2` reaches."""
    reference = pinned_at(parse_model_reference("support/refund-classifier"), "2")

    assert reference.pin == "2"
    assert reference.pinned is True
    assert reference.model_name == "support/refund-classifier"


def test_the_raw_string_is_still_what_the_caller_sent() -> None:
    """A-079 echoes the model field back and a not-found names it. The caller
    wrote `support/refund-classifier`, so that is what both must say — growing
    `raw` into `...@2` would put a string in the response that nobody sent."""
    reference = pinned_at(parse_model_reference("support/refund-classifier"), "2")

    assert reference.raw == "support/refund-classifier"


def test_no_version_leaves_the_reference_exactly_as_parsed() -> None:
    """The overwhelmingly common request, and the one that must cost nothing."""
    parsed = parse_model_reference("support/refund-classifier")

    assert pinned_at(parsed, None) is parsed


def test_a_version_that_agrees_with_the_pin_is_not_a_conflict() -> None:
    """Belt and braces is not a mistake. A client that puts the version in both
    places is saying one thing twice, and refusing it would break an integration
    that is unambiguous about what it wants."""
    reference = pinned_at(parse_model_reference("support/refund-classifier@2"), "2")

    assert reference.pin == "2"


def test_two_different_revisions_in_one_request_is_refused_rather_than_ranked() -> None:
    """Neither field wins. A precedence rule is one more thing an integrator has
    to know to predict which revision they are served, and knowing exactly that
    is the only reason to pin in the first place."""
    with pytest.raises(ModelReferenceConflict) as raised:
        pinned_at(parse_model_reference("support/refund-classifier@2"), "3")

    assert raised.value.pin == "2"
    assert raised.value.version == "3"


def test_a_version_id_folds_in_as_readily_as_a_number() -> None:
    """`@<n>` and `@<version_id>` are different columns one module over, and this
    function is not the place that knows which — it hands over text, exactly as
    the `@` form does."""
    reference = pinned_at(parse_model_reference("support/refund-classifier"), VERSION_ID)

    assert reference.pin == VERSION_ID

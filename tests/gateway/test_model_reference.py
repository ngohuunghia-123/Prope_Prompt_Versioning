"""A-021 and A-022: `namespace/name`, `@<n>`, `@<version_id>`, and every malformed shape.

This is the first thing that touches a consumer's input on the one
internet-facing route, and the parse decides what reaches a database lookup. The
pin is kept OUT of :class:`ModelName` on purpose — `support/refund@3` is a name
and a pin, and merging them is how a pin reaches a unique-constraint lookup.
"""

import pytest

from prope.gateway.domain import ModelReferenceInvalid, parse_model_reference


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

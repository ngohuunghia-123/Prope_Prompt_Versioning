"""A-021's ``namespace/name``, parsed at the edge and passed as a value.

The model name is the string a **consuming product calls**. It reaches Prope as
an OpenAI ``model`` field from a client nobody here controls, and it is immutable
once created — so every rule about its shape has to be decided once, at the parse,
rather than inferred at each of the places it is compared.

The pattern here is byte-identical to ``ck_prompt_property_namespace_shape`` and
``ck_prompt_property_name_shape``. Two spellings of one rule is two things to keep
in step, and the first drift would be invisible in both directions: the database
would refuse a name this parser accepted, and the caller would meet a constraint
name they cannot act on.
"""

import pytest

from prope.prompt_registry.domain import ModelName, ModelNameInvalid


def test_a_well_formed_name_round_trips() -> None:
    parsed = ModelName.parse("support/refund-classifier")

    assert parsed.namespace == "support"
    assert parsed.name == "refund-classifier"
    assert str(parsed) == "support/refund-classifier"


def test_a_bare_name_is_refused() -> None:
    """A-021 makes the name ``namespace/name``, and the namespace is not optional.

    A bare name would be unique per workspace only by accident, and the accident
    would surface as two teams' prompts colliding on the day the second one was
    registered.
    """
    with pytest.raises(ModelNameInvalid) as refused:
        ModelName.parse("refund-classifier")

    assert "namespace/name" in str(refused.value)


def test_a_path_shaped_name_is_refused() -> None:
    """The name is one segment, not a path.

    Worth refusing explicitly rather than letting the pattern catch it: a caller
    who wrote ``support/refunds/classifier`` meant something, and a message about
    a character class would not tell them what.
    """
    with pytest.raises(ModelNameInvalid) as refused:
        ModelName.parse("support/refunds/classifier")

    assert "one segment" in str(refused.value)


@pytest.mark.parametrize(
    "raw",
    [
        "Support/refund",
        "support/Refund",
        "-support/refund",
        "support/-refund",
        "support/",
        "/refund",
        "support/refund classifier",
        "support/refund@2",
        "sup port/refund",
        "s" * 64 + "/refund",
        "support/" + "r" * 64,
    ],
)
def test_shapes_the_pattern_refuses(raw: str) -> None:
    """Upper case, a leading punctuation character, a space, an empty half, and
    both halves over 63 characters.

    Lower case only because a model name is retyped by hand into client code, and
    a case-sensitive lookup on a value people retype is a support conversation
    nobody wins. ``@`` is refused because it is the PIN separator — a name
    carrying one would make ``support/refund@2`` ambiguous between a pinned
    resolution and a prompt somebody named oddly.
    """
    with pytest.raises(ModelNameInvalid):
        ModelName.parse(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "support/refund-classifier",
        "a/b",
        "support2/v1.2",
        "internal_tools/summariser",
        "s" * 63 + "/" + "r" * 63,
    ],
)
def test_shapes_the_pattern_accepts(raw: str) -> None:
    """Dots, underscores and hyphens after the first character, and 63 each.

    The positive half matters as much as the negative one: a pattern that refused
    everything would pass every test above and make the product unusable.
    """
    assert str(ModelName.parse(raw)) == raw


def test_the_value_is_frozen() -> None:
    """Immutable once created (A-021), enforced by the type rather than by care.

    A ``ModelName`` a handler could mutate is a handler that could resolve one
    prompt and serve another.
    """
    parsed = ModelName.parse("support/refund-classifier")

    with pytest.raises((AttributeError, TypeError)):
        parsed.name = "something-else"  # type: ignore[misc]


def test_two_equal_names_compare_equal() -> None:
    """A frozen dataclass, so equality is by value.

    Load-bearing wherever a resolved name is compared against a scope entry: an
    identity comparison would answer ``False`` for two parses of one string, and
    the failure would look like a key-scope refusal.
    """
    assert ModelName.parse("a/b") == ModelName.parse("a/b")
    assert ModelName.parse("a/b") != ModelName.parse("a/c")

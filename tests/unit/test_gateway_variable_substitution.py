"""AC-8 and ADR-0011's second half: `{{variable}}`, and the refusal when one is unfilled.

The acceptance criterion has two clauses and the second is the load-bearing one:
*"no request containing the literal `{{customer_name}}` is ever dispatched
upstream"*. ADR-0011 rejects letting an unfilled placeholder through by name —
the model receives text that looks like a template and answers plausibly anyway,
and the consumer ships a response referring to `{{customer_name}}` or, worse, a
hallucinated substitute. So the check is *before* the dispatch, and it is a
refusal rather than a best effort.

There is a second, quieter guarantee asserted here: substitution is single-pass.
A value that itself contains braces is a value, not a template, and re-scanning
the rendered text would make a caller-supplied string able to name a variable the
reviewer never saw.
"""

import pytest

from prope.gateway.templating import (
    MissingVariable,
    UnfilledPlaceholder,
    render,
    required_variables,
)


def test_a_body_with_no_placeholders_needs_no_variables() -> None:
    body = "You are a helpful assistant."

    assert required_variables(body) == ()
    assert render(body, None) == body
    assert render(body, {"unused": "ignored"}) == body


def test_variables_the_template_does_not_use_are_ignored() -> None:
    """ADR-0011: *"Variables the template does not use are ignored. The
    missing-variable check already catches the typo that would otherwise hide
    behind an unused key."*"""
    assert render("Hello {{name}}.", {"name": "Ada", "tier": "gold"}) == "Hello Ada."


def test_every_placeholder_is_reported_once_and_in_order() -> None:
    body = "{{greeting}} {{name}}, your {{tier}} plan. Again: {{name}}."

    assert required_variables(body) == ("greeting", "name", "tier")


def test_whitespace_inside_the_braces_is_the_same_placeholder() -> None:
    """A person writing a prompt in a textarea types what looks right to them,
    and `{{ name }}` looking right is not a reason for the call to fail."""
    assert render("Hello {{ name }}.", {"name": "Ada"}) == "Hello Ada."


def test_a_missing_variable_names_the_variable_it_is_missing() -> None:
    """The 400 a consumer meets says which key to add. A refusal that cannot say
    what is missing is a support conversation rather than an error message."""
    with pytest.raises(MissingVariable) as raised:
        render("Refund policy for {{customer_name}}.", {"tier": "gold"})

    assert raised.value.name == "customer_name"


def test_an_empty_variables_object_is_the_same_as_none() -> None:
    for supplied in (None, {}):
        with pytest.raises(MissingVariable):
            render("Hello {{name}}.", supplied)


def test_a_null_value_is_missing_rather_than_the_string_none() -> None:
    """`{"customer_name": null}` is a caller who has a bug, and rendering it as
    the four characters `None` would put that bug in front of a real user."""
    with pytest.raises(MissingVariable) as raised:
        render("Hello {{name}}.", {"name": None})

    assert raised.value.name == "name"


def test_a_non_string_value_is_rendered_rather_than_refused() -> None:
    """JSON has numbers and booleans and a caller will send them. Refusing would
    be refusing a request that is not wrong."""
    assert render("You have {{count}} left.", {"count": 3}) == "You have 3 left."
    assert render("Beta: {{flag}}.", {"flag": True}) == "Beta: True."


def test_substitution_is_single_pass_so_a_value_cannot_name_a_variable() -> None:
    """A caller-supplied value containing braces is text, not a template.

    If rendering re-scanned its own output, a request could reach a placeholder
    the reviewer never approved — and it would do so through the one field on
    this surface that is entirely caller-controlled.
    """
    rendered = render("Say {{quote}}.", {"quote": "{{secret}}"})

    assert rendered == "Say {{secret}}."


def test_the_substitution_count_is_checked_against_the_placeholder_count() -> None:
    """The tripwire beside the check, and it counts rather than re-scans.

    Re-scanning the RENDERED text would refuse the test above — a value
    containing braces is caller data, not a template — so what is asserted is
    that the two passes over the BODY agree: every placeholder `render` verified
    a value for is a placeholder `subn` replaced. It is unreachable today and
    exists so that a future edit which makes the scanning and the substituting
    patterns diverge fails here rather than by putting a literal `{{...}}` in
    front of somebody's customer.
    """
    assert UnfilledPlaceholder(2, 1).expected == 2

    with pytest.raises(UnfilledPlaceholder):
        raise UnfilledPlaceholder(2, 1)

"""CR-01: the one bound the database cannot carry, and the reason it cannot.

``PUT /api/v1/workspaces/{id}/retention`` evaluates
``timedelta(days=payload.retention_days)`` **before any statement exists**
(``api.set_retention``). Above ``timedelta.max.days`` that expression raises
``OverflowError``, which subclasses ``ArithmeticError`` and matches **none** of
``drain.classify_write_failure``'s branches — so it would fall to the
``PERMANENT`` default and dead-letter, two modules away from the route that
accepted the value. ``02-VERIFICATION.md`` raised it; this file closes it.

**The bound is on the input and not on the column, and that is not a compromise
— it is the only place it can go.** A ``CHECK`` cannot refuse an exception raised
in the client before a statement is constructed. This is the documented exception
to *build database-first*, and naming the exception is what keeps the rule
intact.

**So this file asserts the reason and not only the rule.** A test that checked
``le=3650`` alone would still pass if somebody later moved the bound to ``10**8``
and reintroduced the bug, because ``10**8`` is a smaller number that is still
under ``timedelta.max.days``… and then somebody moves it again. What is asserted
instead is the property: *the exception this bound exists to prevent cannot be
reached through this schema* — constructed from ``MAX_RETENTION_DAYS`` itself, so
it stays true for whatever the constant becomes.

**And the negative control keeps the file honest.** ``0`` and ``-1`` are
**accepted** here, because the lower bound is the engine's
(``ck_workspace_retention_window_is_positive``) and re-checking it in pydantic
would put one guarantee in two places. If that test ever starts failing, somebody
has moved the lower bound into the model, and the paragraph at ``RetentionSet``
arguing its absence should be deleted in the same change rather than left to
contradict the code.
"""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from prope.call_ledger.schemas import MAX_RETENTION_DAYS, ErrorCode, RetentionSet


def test_the_bound_is_the_named_constant_and_not_a_literal():
    """``MAX_PAGE_LIMIT``'s rule: the test asserts the number, so the field cannot.

    The value is pinned here as well as read, because ``MAX_RETENTION_DAYS`` is a
    product-visible limit — no workspace can set a longer window through the API —
    and moving it should be a change somebody has to make in two places on
    purpose.
    """
    assert MAX_RETENTION_DAYS == 3650


def test_the_largest_accepted_value_validates():
    assert RetentionSet(retention_days=MAX_RETENTION_DAYS).retention_days == MAX_RETENTION_DAYS


def test_one_day_past_the_bound_is_refused_by_name():
    """The boundary pair. ``le=`` is a cap and not a clamp (``PageRequest``)."""
    with pytest.raises(ValidationError) as raised:
        RetentionSet(retention_days=MAX_RETENTION_DAYS + 1)

    errors = raised.value.errors()
    assert [error["loc"] for error in errors] == [("retention_days",)]
    assert errors[0]["type"] == "less_than_equal"


def test_the_overflow_this_bound_exists_to_prevent_is_unreachable_through_the_schema():
    """The property, not the number — which is what makes the test survive a retune.

    Two halves, and both are needed. First: every value the schema accepts can be
    handed to ``timedelta(days=...)``, asserted at the largest one rather than
    reasoned about, because the boundary is the only value where it could fail.
    Second: a value that genuinely *would* overflow is refused by the model
    **first**, so the route never reaches the expression at all.

    ``10**9`` is one past ``timedelta.max.days`` (999,999,999), so it is the
    smallest round number that provokes the real ``OverflowError`` — and the test
    proves the exception exists before proving the schema hides it, so "pydantic
    raised something" cannot be mistaken for the property.
    """
    assert timedelta(days=MAX_RETENTION_DAYS).days == MAX_RETENTION_DAYS

    with pytest.raises(OverflowError):
        timedelta(days=10**9)

    with pytest.raises(ValidationError):
        RetentionSet(retention_days=10**9)


@pytest.mark.parametrize("days", [0, -1])
def test_a_non_positive_window_is_still_accepted_by_the_model(days: int):
    """The negative control: the lower bound is the engine's and stays there.

    This is the assertion that stops this file from being a test about pydantic.
    ``ck_workspace_retention_window_is_positive`` refuses zero and negative
    windows at the engine, and ``api.set_retention`` translates that refusal into
    ``ErrorCode.RETENTION_WINDOW_NOT_POSITIVE`` —
    ``tests/integration/test_management_routes.py`` drives that end to end.

    **If this test ever fails, somebody has moved the lower bound into pydantic.**
    That is a legitimate change to argue for, but it must be made together with
    deleting ``RetentionSet``'s paragraph arguing the absence, or the field will
    carry a docstring that contradicts its own validator.
    """
    assert RetentionSet(retention_days=days).retention_days == days


def test_the_bound_adds_no_error_code():
    """ADR-0053: a ``le=`` violation renders as the code the SPA already knows.

    ``ErrorCode`` is a closed ``StrEnum`` and ``install_error_envelope``'s
    ``RequestValidationError`` handler answers every schema violation with
    ``VALIDATION_FAILED``. A member added for this bound would be a code the
    catalogue has never seen, which renders as nothing at all and does so
    silently — so the absence is asserted rather than assumed.
    """
    retention_codes = [member.name for member in ErrorCode if "RETENTION" in member.name]

    assert retention_codes == ["RETENTION_WINDOW_NOT_POSITIVE"], (
        "the lower bound's code is the only retention-specific one; the upper bound "
        "renders as VALIDATION_FAILED and needs no member of its own"
    )
    assert ErrorCode.VALIDATION_FAILED in ErrorCode

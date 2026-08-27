"""ADR-0069's two closed decisions, held as tables rather than as prose.

`RevisionBinding.candidates` is what makes the gateway loop single-path: a
pair-bound revision is a ONE-ENTRY ROUTE, so the unrouted case — nearly all
traffic — is the loop's degenerate case rather than a second branch beside it.
Two branches is where they drift, and the drift would show up as a routed
revision serving from the wrong rung, which nothing else on the path can see.

`_advances` is asserted as a **total table over every `ErrorClass` member**, so
a new class fails this test until somebody classifies it. That is the point:
the default for an unclassified failure would otherwise be silence, and silence
here means either a route that stops for a failure another provider could have
answered, or a request walked to a second provider that should never have left
the first.
"""

import pytest

from prope.gateway.routes import ADVANCING, ADVANCING_CONFIGURATION, _advances
from prope.prompt_registry.domain import RevisionBinding, RouteEntry
from prope.provider_access.domain import DispatchError, ErrorClass
from prope.provider_access.failures import CLASSIFICATION

#: Every class, and what the loop must do with it. Spelled out rather than
#: derived, because deriving it from `CLASSIFICATION` here would restate the
#: implementation and assert nothing.
EXPECTED = {
    # Provider failures: another provider could plausibly answer.
    ErrorClass.RATE_LIMITED: True,
    ErrorClass.CREDENTIAL_REJECTED: True,
    ErrorClass.MODEL_UNAVAILABLE: True,
    ErrorClass.UPSTREAM_UNAVAILABLE: True,
    ErrorClass.UPSTREAM_TIMEOUT: True,
    ErrorClass.CONTRACT_VIOLATION: True,
    ErrorClass.ADMISSION_REFUSED: True,
    # Facts about ONE configuration, and the case a combo exists for: an admin
    # disabled a provider this morning. NOT fallback-eligible and must not
    # become so — ADR-0013's rule is that a Prope-side misconfiguration is never
    # papered over with canned text, which is a claim about the canned answer
    # and not about the next provider.
    ErrorClass.CONFIGURATION_UNUSABLE: True,
    ErrorClass.BLOCKED_ADDRESS: True,
    # Facts about the REQUEST. Advancing on a policy refusal is policy-shopping;
    # a malformed request fails identically everywhere.
    ErrorClass.CONTENT_POLICY: False,
    ErrorClass.INVALID_REQUEST: False,
    # No KEK in this process means every entry fails the same way, so advancing
    # only burns the budget without ever reaching a working rung.
    ErrorClass.KEY_UNAVAILABLE: False,
}


def _error(error_class: ErrorClass) -> DispatchError:
    """Built from the closed table, not by hand.

    A hand-written `fallback_eligible` here would let this file disagree with
    the classification it is supposed to be reading, which is the one way these
    assertions could be green and wrong at the same time.
    """
    facts = CLASSIFICATION[error_class]
    return DispatchError(
        error_class=facts.error_class,
        origin=facts.origin,
        fallback_eligible=facts.fallback_eligible,
        retryable=facts.retryable,
        message="upstream is unwell",
    )


def test_the_table_covers_every_error_class() -> None:
    """The guard that stops the parametrised test below passing vacuously.

    A new `ErrorClass` fails here first, with a message naming it, rather than
    silently taking whichever branch `_advances` happens to fall into.
    """
    assert set(EXPECTED) == set(ErrorClass), (
        f"unclassified: {sorted(c.value for c in set(ErrorClass) - set(EXPECTED))}"
    )


@pytest.mark.parametrize("error_class", sorted(ErrorClass, key=lambda member: member.value))
def test_advancing_is_decided_for_every_class(error_class: ErrorClass) -> None:
    assert _advances(_error(error_class)) is EXPECTED[error_class]


def test_the_advancing_set_is_derived_from_fallback_eligible_and_not_typed_out() -> None:
    """`fallback_eligible` already means *"this failure is about the provider,
    not about the request"* — which is exactly what *"should somebody else try
    it"* asks. Deriving it is what keeps the two answers from drifting apart."""
    assert ADVANCING == frozenset(k for k, v in CLASSIFICATION.items() if v.fallback_eligible)


def test_the_two_configuration_classes_advance_without_becoming_fallback_eligible() -> None:
    """The one place ADR-0069 splits a question one flag was answering.

    `_advances()` decides the loop; `error.fallback_eligible` still decides the
    canned answer. If every rung is misconfigured the caller gets a 500 and
    never canned text, which is ADR-0013's rule left intact.
    """
    assert ADVANCING_CONFIGURATION == {ErrorClass.CONFIGURATION_UNUSABLE, ErrorClass.BLOCKED_ADDRESS}
    for error_class in ADVANCING_CONFIGURATION:
        assert CLASSIFICATION[error_class].fallback_eligible is False
        assert _advances(_error(error_class)) is True


def _routed(*entries: tuple[int, str, str]) -> RevisionBinding:
    return RevisionBinding(
        prompt_id="prm_1",
        version_id="rev_1",
        revision_number=1,
        body="hello",
        parameters={},
        fallback_answer=None,
        provider_config_id=None,
        upstream_model=None,
        route_combo_id="rtc_1",
        route_combo_name="Primary and backup",
        route=tuple(RouteEntry(*entry) for entry in entries),
    )


def _paired() -> RevisionBinding:
    return RevisionBinding(
        prompt_id="prm_1",
        version_id="rev_1",
        revision_number=1,
        body="hello",
        parameters={},
        fallback_answer=None,
        provider_config_id="prv_1",
        upstream_model="gpt-4o-mini",
    )


def _unbound() -> RevisionBinding:
    return RevisionBinding(
        prompt_id="prm_1",
        version_id="rev_1",
        revision_number=1,
        body="hello",
        parameters={},
        fallback_answer=None,
        provider_config_id=None,
        upstream_model=None,
    )


def test_a_pair_is_a_one_entry_route() -> None:
    """The whole reason the loop has no second branch."""
    binding = _paired()

    assert binding.routed is False
    assert binding.candidates == (RouteEntry(1, "prv_1", "gpt-4o-mini"),)


def test_a_route_is_walked_in_priority_order() -> None:
    binding = _routed((1, "prv_1", "gpt-4o-mini"), (2, "prv_2", "gpt-4o"))

    assert binding.routed is True
    assert [entry.priority for entry in binding.candidates] == [1, 2]
    assert binding.candidates[0].provider_config_id == "prv_1"


def test_an_unbound_revision_has_no_candidates() -> None:
    """Which is what the gateway turns into a 500 rather than a canned answer:
    a revision nobody finished binding is a Prope-side configuration problem,
    and ADR-0013 refuses to paper those over."""
    assert _unbound().candidates == ()
    assert _unbound().routed is False


def test_a_half_binding_has_no_candidates_either() -> None:
    """`ck_revision_binding_is_whole` refuses this row, so it should be
    unreachable — and the property answers it safely anyway rather than
    composing a candidate with a `None` model."""
    half = RevisionBinding(
        prompt_id="prm_1",
        version_id="rev_1",
        revision_number=1,
        body="hello",
        parameters={},
        fallback_answer=None,
        provider_config_id="prv_1",
        upstream_model=None,
    )

    assert half.candidates == ()

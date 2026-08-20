"""AC-1. Every detector fires on synthetic counts and stays quiet on a healthy pair.

**No database, no model, no provider, and no prompt body anywhere in this file.**
That is the acceptance criterion and not an incidental property of how the tests
were written: ADR-0068 §1 says the evidence is metadata arithmetic, and the proof
that it is arithmetic is that the whole detector set can be exercised from
integers. A fixture here that needed a prompt body would mean the claim had
quietly stopped being true.

**The control case is tested for every detector, not once.** A detector that fires
on a healthy window is worse than one that never fires — deck 6 slide 64's alert
fatigue, manufactured by the arithmetic — and a suite that only asserts the
positive direction cannot tell the difference between a working threshold and
``return Anomaly(...)``.
"""

from datetime import UTC, datetime, timedelta

import pytest

from prope.prompt_improvement import detectors
from prope.prompt_improvement.domain import (
    DEFAULT_SEVERITY,
    REMEDY_KIND,
    Anomaly,
    DetectorId,
    RemedyKind,
    WindowPair,
)
from tests.prompt_improvement import pair, window

NOW = datetime(2026, 8, 20, tzinfo=UTC)


def test_a_healthy_pair_produces_nothing() -> None:
    """**Empty is the success condition** (A-162's inversion, ADR-0064's shape).

    The sweep writes no row for this pair, so an inbox is empty for a workspace
    whose prompts are all behaving — which is what makes a non-empty one worth
    opening.
    """
    assert detectors.run_ledger_detectors(WindowPair(current=window(), prior=window())) == ()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"fallback": 60}, DetectorId.FALLBACK_RISING),
        ({"truncated": 60}, DetectorId.TRUNCATION_RISING),
        ({"caller_error": 60}, DetectorId.CALLER_ERROR_CLUSTERING),
        ({"chained": 60}, DetectorId.CHAIN_DEPTH_RISING),
        ({"pinned": 60}, DetectorId.PINNED_SHARE_RISING),
        ({"output_tokens": 400_000}, DetectorId.OUTPUT_RATIO_DRIFT),
        ({"usage_unknown": 12}, DetectorId.USAGE_UNKNOWN_APPEARING),
        ({"cost_unpriced": 12}, DetectorId.COST_UNPRICED_APPEARING),
        ({"latency_p95_ms": 4_000}, DetectorId.LATENCY_TAIL_SHIFT),
    ],
)
def test_each_ledger_detector_fires_on_its_own_column(
    overrides: dict[str, int], expected: DetectorId
) -> None:
    """One moved column, one detector.

    Each row moves exactly one field of an otherwise healthy window, so a
    detector that reached into a column it does not own shows up as a second
    ``detector_id`` in the result rather than as a passing test.
    """
    found = detectors.run_ledger_detectors(pair(**overrides))

    assert [anomaly.detector_id for anomaly in found] == [expected]


def test_nothing_fires_below_the_request_floor() -> None:
    """**A rate computed from nine calls is not a rate.**

    Both windows are entirely fallback — the most extreme degradation the ledger
    can express — and nothing fires, because there is not enough traffic for the
    share to mean anything. Losing a real regression on a quiet prompt is the
    accepted cost, and it is cheaper than teaching somebody that this module
    cries wolf.
    """
    tiny = WindowPair(
        current=window(requests=detectors.MIN_REQUESTS - 1, fallback=detectors.MIN_REQUESTS - 1),
        prior=window(requests=detectors.MIN_REQUESTS - 1),
    )

    assert detectors.run_ledger_detectors(tiny) == ()


def test_a_share_must_both_multiply_and_move() -> None:
    """Relative alone fires on noise; absolute alone re-fires on a known break.

    Two assertions, one per half of ``_rose``. The first quadruples a share that
    is a rounding error and must stay quiet. The second adds five points to a
    prompt that has been half-broken all week, and must also stay quiet — its
    finding is already open, and a second one would be the same fact twice.
    """
    quadrupled_from_nothing = WindowPair(
        current=window(requests=1_000, fallback=8),
        prior=window(requests=1_000, fallback=2),
    )
    assert detectors.fallback_rising(quadrupled_from_nothing) is None

    already_broken = WindowPair(
        current=window(requests=1_000, fallback=450),
        prior=window(requests=1_000, fallback=400),
    )
    assert detectors.fallback_rising(already_broken) is None


def test_usage_unknown_fires_on_appearance_and_not_on_a_rise() -> None:
    """A-101. **Missing is not zero**, and the event is the first day of missing.

    A proportional threshold would let a silently degrading provider pass
    unremarked for the days somebody would most want back. Once the prior window
    already had some, the finding is open and this stays quiet.
    """
    appeared = detectors.usage_unknown_appearing(pair(usage_unknown=12))
    assert appeared is not None
    assert appeared.detector_id is DetectorId.USAGE_UNKNOWN_APPEARING

    already_missing = WindowPair(
        current=window(usage_unknown=80),
        prior=window(usage_unknown=12),
    )
    assert detectors.usage_unknown_appearing(already_missing) is None


def test_the_output_ratio_ignores_a_window_with_no_reported_usage() -> None:
    """An outage must not read as a dramatic cost improvement.

    A window whose provider stopped reporting has an input-token sum of zero. A
    ratio computed against it either divides by nothing or reports the prompt got
    wonderfully terse, and the second is worse — it is good news generated by a
    fault, and it has its own detector.
    """
    silent_provider = WindowPair(
        current=window(input_tokens=0, output_tokens=0),
        prior=window(),
    )

    assert detectors.output_ratio_drift(silent_provider) is None


def test_pinned_share_needs_an_absolute_floor_as_well_as_a_rise() -> None:
    """The governance signal, and the reason it carries a floor.

    A workspace where a tenth of traffic deliberately does not take what was
    released is worth saying out loud. A workspace where that share went from
    0.2% to 0.8% is not — the release record and production still agree about
    substantially all of the traffic.
    """
    below_the_floor = WindowPair(
        current=window(requests=1_000, pinned=80),
        prior=window(requests=1_000, pinned=2),
    )
    assert detectors.pinned_share_rising(below_the_floor) is None

    above_it = detectors.pinned_share_rising(
        WindowPair(current=window(requests=1_000, pinned=300), prior=window(requests=1_000))
    )
    assert above_it is not None
    assert above_it.params["share"] == 0.3


def test_released_but_unused_needs_both_windows_empty_and_an_old_release() -> None:
    """A prompt that was quiet yesterday is not a prompt nobody calls."""
    silent = WindowPair(current=window(requests=0), prior=window(requests=0))
    long_ago = NOW - timedelta(days=90)

    found = detectors.released_but_unused(silent, released_at=long_ago, now=NOW)
    assert found is not None
    assert found.params["days_since_release"] == 90

    # Released last week: not yet evidence of anything.
    assert detectors.released_but_unused(silent, released_at=NOW - timedelta(days=3), now=NOW) is None
    # Never released: there is no release to be unused.
    assert detectors.released_but_unused(silent, released_at=None, now=NOW) is None
    # Busy yesterday.
    yesterday = WindowPair(current=window(requests=0), prior=window(requests=500))
    assert detectors.released_but_unused(yesterday, released_at=long_ago, now=NOW) is None


def test_profile_drift_names_the_axis_that_moved() -> None:
    """*Serving the public; approved as internal.* **ADR-0067 D-02's payoff.**

    ``params`` has to name WHICH axis moved and in which direction, because
    *"the profile changed"* is not actionable and *"audience: internal ->
    public"* is. The assertion is on the contents rather than on the presence of
    the key, since a detector that reported drift without the direction would
    still pass a presence check.
    """
    declared = {
        "audience": "public",
        "untrusted_input": "none",
        "acts": "answers_only",
        "sensitivity": "synthetic",
    }
    stamped = {**declared, "audience": "internal"}

    found = detectors.profile_drift(declared, stamped)

    assert found is not None
    assert found.detector_id is DetectorId.PROFILE_DRIFT
    assert found.params["axes"] == {"audience": {"stamped": "internal", "declared": "public"}}
    assert detectors.profile_drift(declared, declared) is None


def test_profile_drift_is_undetectable_without_a_stamp() -> None:
    """No stamp, no right-hand side. Silence, never a guess.

    A revision released before ``0030_usage_profile.py`` has nothing stamped on
    it. The honest answer is that the comparison cannot be made — and inferring
    the missing side from the body is exactly what A-163 forbids, so the
    detector returns ``None`` rather than reporting drift against an assumption.
    """
    declared = {"audience": "public"}

    assert detectors.profile_drift(declared, None) is None
    assert detectors.profile_drift(declared, {}) is None
    assert detectors.profile_drift(None, {"audience": "internal"}) is None


def test_probe_leak_fires_on_a_single_new_leak() -> None:
    """One is enough, because the pre-release probe established these were refused.

    Deck 6 slide 25's drift: the guardrail became bypassable and nothing errored.
    A proportional threshold would mean the first case to start leaking is
    ignored, which is the case that says the model changed underneath.
    """
    found = detectors.probe_leak_appeared(current_leaked=1, prior_leaked=0, cases=12)

    assert found is not None
    assert found.params == {"leaked": 1, "prior_leaked": 0, "cases": 12}
    # Unchanged, improved, or no cases at all: nothing to say.
    assert detectors.probe_leak_appeared(current_leaked=1, prior_leaked=1, cases=12) is None
    assert detectors.probe_leak_appeared(current_leaked=0, prior_leaked=3, cases=12) is None
    assert detectors.probe_leak_appeared(current_leaked=5, prior_leaked=0, cases=0) is None


def test_the_ranking_order_leads_with_the_answer_users_are_getting() -> None:
    """When the triage model is unavailable, ``DETECTORS`` order is the ranking.

    ``fallback_rising`` first is the judgement being asserted: it is the one
    anomaly here that means somebody asking a question right now is getting a
    worse answer. The degraded path in ``triage`` returns this order verbatim,
    so this tuple is a product decision and not an implementation detail.
    """
    both = WindowPair(
        current=window(fallback=60, latency_p95_ms=4_000),
        prior=window(),
    )

    found = detectors.run_ledger_detectors(both)

    assert [anomaly.detector_id for anomaly in found] == [
        DetectorId.FALLBACK_RISING,
        DetectorId.LATENCY_TAIL_SHIFT,
    ]


def test_every_detector_has_a_severity_and_a_remedy_kind() -> None:
    """The two maps are total over the catalogue, checked here rather than assumed.

    ``Anomaly.severity`` and ``Anomaly.remedy_kind`` index these maps directly, so
    a thirteenth detector added without an entry is a ``KeyError`` inside the
    sweep — during a background job, against one workspace, where it would be
    seen late if at all.
    """
    assert set(DEFAULT_SEVERITY) == set(DetectorId)
    assert set(REMEDY_KIND) == set(DetectorId)


def test_only_a_detector_with_a_reachable_family_may_propose_an_edit() -> None:
    """ADR-0068 §3, as an invariant over the two maps.

    ``remedy_kind == edit`` and an empty ``reachable_families`` would be a
    proposal that must carry a body and has no sanctioned transform to produce
    one — which is the door to free-form rewriting, opened by omission rather
    than by decision.
    """
    for detector_id in DetectorId:
        anomaly = Anomaly(detector_id=detector_id)
        if anomaly.remedy_kind is RemedyKind.EDIT:
            assert anomaly.reachable_families, detector_id
        else:
            assert anomaly.reachable_families == (), detector_id


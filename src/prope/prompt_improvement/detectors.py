"""Twelve pure functions. No model, no database, no prompt body, no I/O at all.

**This is the half that carries the facts, and it is the reason the module is
defensible.** Every function here answers a question with arithmetic:
``outcome=fallback`` went from 1% to 22%. Nothing asks a model whether it agrees,
because the model would be agreeing with a number.

**Pure by construction, not by convention.** Each detector takes a
:class:`WindowPair` and returns an :class:`Anomaly` or ``None``, and nothing in
this file imports a session, a client or a settings object. AC-1 tests every one
of them against hand-built windows with no fixtures containing prompt bodies —
which is only possible because the input is counts.

**Two detectors take something other than a window pair**, and their signatures
say so rather than smuggling extra state into the pair. ``profile_drift``
compares two declarations; ``probe_leak_appeared`` compares two probe runs.
Neither reads the ledger at all.

**Thresholds are constants at the top of this file and every one of them is a
judgement.** They are gathered here rather than inlined so that changing one is a
visible act, and they are unvalidated at real scale like every number of this
kind in this repository. The dismissal rate per ``detector_id`` is what would
justify moving any of them (OQ-157).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Final

from prope.prompt_improvement.domain import Anomaly, DetectorId, WindowPair

__all__ = [
    "DETECTORS",
    "MIN_REQUESTS",
    "caller_error_clustering",
    "chain_depth_rising",
    "cost_unpriced_appearing",
    "fallback_rising",
    "latency_tail_shift",
    "output_ratio_drift",
    "pinned_share_rising",
    "probe_leak_appeared",
    "profile_drift",
    "released_but_unused",
    "run_ledger_detectors",
    "truncation_rising",
    "usage_unknown_appearing",
]

#: Below this many requests in a window, nothing fires. **A rate computed from
#: nine calls is not a rate**, and a detector that opened a finding because one
#: of five calls truncated would train somebody to dismiss the whole module
#: within a week — deck 6 slide 64, self-inflicted at the arithmetic level.
MIN_REQUESTS: Final = 30

#: How much a share must move before it is a signal rather than noise. Both
#: halves matter: a RELATIVE rise catches 1% -> 4% on a healthy prompt, and an
#: ABSOLUTE floor stops 0.1% -> 0.4% from qualifying as the same event.
RELATIVE_RISE: Final = 2.0
ABSOLUTE_RISE: Final = 0.05

#: The output-to-input ratio has to move further than a rate does, because it
#: drifts naturally with the questions being asked. Output costs five to six
#: times input, so a 40% move here is a real bill.
RATIO_RISE: Final = 1.4

#: The latency tail. A 50% p95 move is the smallest thing that shows up as
#: "it got slow" to a person using the product it serves.
LATENCY_RISE: Final = 1.5

#: A share of pinned traffic that has grown past this is a governance signal:
#: consumers are deliberately not taking what was released.
PINNED_SHARE_FLOOR: Final = 0.10

#: Released this long ago with no traffic at all in the window.
UNUSED_AFTER: Final = timedelta(days=60)


def _share(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _rose(current: float, prior: float) -> bool:
    """A share that both multiplied and moved by an absolute amount.

    Two conditions rather than one, because either alone is wrong in a way that
    produces findings nobody wants. Relative alone fires on 0.1% -> 0.4%.
    Absolute alone fires on 40% -> 45% on a prompt that has been broken all week
    and whose finding is already open.
    """
    if current - prior < ABSOLUTE_RISE:
        return False
    if prior == 0.0:
        return True
    return current / prior >= RELATIVE_RISE


def _rate_detector(
    detector_id: DetectorId, attribute: str
) -> Callable[[WindowPair], Anomaly | None]:
    """The five detectors that are the same arithmetic over a different column.

    Written as a factory rather than five near-identical functions, because five
    copies of a threshold comparison is five places for one of them to be edited
    and the others not — and the resulting disagreement would be invisible.
    """

    def detect(windows: WindowPair) -> Anomaly | None:
        current, prior = windows.current, windows.prior
        if current.requests < MIN_REQUESTS or prior.requests < MIN_REQUESTS:
            return None

        now = _share(getattr(current, attribute), current.requests)
        before = _share(getattr(prior, attribute), prior.requests)
        if not _rose(now, before):
            return None

        return Anomaly(
            detector_id=detector_id,
            params={
                "share": round(now, 4),
                "prior_share": round(before, 4),
                "count": getattr(current, attribute),
                "requests": current.requests,
            },
        )

    detect.__name__ = str(detector_id)
    return detect


truncation_rising = _rate_detector(DetectorId.TRUNCATION_RISING, "truncated")
fallback_rising = _rate_detector(DetectorId.FALLBACK_RISING, "fallback")
caller_error_clustering = _rate_detector(DetectorId.CALLER_ERROR_CLUSTERING, "caller_error")
chain_depth_rising = _rate_detector(DetectorId.CHAIN_DEPTH_RISING, "chained")


def output_ratio_drift(windows: WindowPair) -> Anomaly | None:
    """The model got chattier, which is the largest silent cost regression there is.

    Guarded on both windows having reported usage. A window whose provider stopped
    reporting has an input-token sum of zero, and a ratio computed against it
    would divide by nothing or — worse — read as a dramatic improvement. That
    case has its own detector, and conflating them would hide an outage behind
    good news.
    """
    current, prior = windows.current, windows.prior
    if current.requests < MIN_REQUESTS or prior.requests < MIN_REQUESTS:
        return None
    if not current.input_tokens or not prior.input_tokens:
        return None

    now = current.output_tokens / current.input_tokens
    before = prior.output_tokens / prior.input_tokens
    if before == 0.0 or now / before < RATIO_RISE:
        return None

    return Anomaly(
        detector_id=DetectorId.OUTPUT_RATIO_DRIFT,
        params={
            "ratio": round(now, 3),
            "prior_ratio": round(before, 3),
            "output_tokens": current.output_tokens,
            "input_tokens": current.input_tokens,
        },
    )


def usage_unknown_appearing(windows: WindowPair) -> Anomaly | None:
    """The provider stopped reporting usage. **Missing, not zero** (A-101).

    Fires on APPEARANCE rather than on a rise: a window that had none and now has
    some is the event, because every cost figure computed after it is absent and
    a dashboard rendering absence as zero reports an outage as thrift. A
    proportional threshold would let the first few days of a silent provider pass
    unremarked, which is exactly the period somebody would want back.
    """
    current, prior = windows.current, windows.prior
    if current.requests < MIN_REQUESTS:
        return None
    if current.usage_unknown == 0 or prior.usage_unknown > 0:
        return None

    return Anomaly(
        detector_id=DetectorId.USAGE_UNKNOWN_APPEARING,
        params={"count": current.usage_unknown, "requests": current.requests},
    )


def cost_unpriced_appearing(windows: WindowPair) -> Anomaly | None:
    """A new upstream model is serving traffic with no price row behind it.

    Appearance again, for `usage_unknown_appearing`'s reason: the cost of the
    traffic in this window is unknowable and will stay unknowable, because a
    price row added tomorrow does not reprice yesterday (ADR-0019 stores the row
    that produced a figure precisely so it cannot).
    """
    current, prior = windows.current, windows.prior
    if current.requests < MIN_REQUESTS:
        return None
    if current.cost_unpriced == 0 or prior.cost_unpriced > 0:
        return None

    return Anomaly(
        detector_id=DetectorId.COST_UNPRICED_APPEARING,
        params={"count": current.cost_unpriced, "requests": current.requests},
    )


def latency_tail_shift(windows: WindowPair) -> Anomaly | None:
    """The tail is the experience and the mean hides it (deck 6 slide 18)."""
    current, prior = windows.current, windows.prior
    if current.requests < MIN_REQUESTS or prior.requests < MIN_REQUESTS:
        return None
    if not current.latency_p95_ms or not prior.latency_p95_ms:
        return None
    if current.latency_p95_ms / prior.latency_p95_ms < LATENCY_RISE:
        return None

    return Anomaly(
        detector_id=DetectorId.LATENCY_TAIL_SHIFT,
        params={
            "p95_ms": current.latency_p95_ms,
            "prior_p95_ms": prior.latency_p95_ms,
            "p99_ms": current.latency_p99_ms,
        },
    )


def pinned_share_rising(windows: WindowPair) -> Anomaly | None:
    """**Consumers are pinning away from the released revision.**

    A governance signal no competitor has, because no competitor is on the
    request path. It carries an absolute FLOOR as well as a rise: a workspace
    where a tenth of traffic has deliberately not taken what was released is
    worth saying out loud even if that tenth arrived gradually, because the
    release-approval record says one thing and production says another.
    """
    current, prior = windows.current, windows.prior
    if current.requests < MIN_REQUESTS or prior.requests < MIN_REQUESTS:
        return None

    now = _share(current.pinned, current.requests)
    before = _share(prior.pinned, prior.requests)
    if now < PINNED_SHARE_FLOOR or not _rose(now, before):
        return None

    return Anomaly(
        detector_id=DetectorId.PINNED_SHARE_RISING,
        params={
            "share": round(now, 4),
            "prior_share": round(before, 4),
            "pinned": current.pinned,
            "requests": current.requests,
        },
    )


def released_but_unused(
    windows: WindowPair, *, released_at: datetime | None, now: datetime
) -> Anomaly | None:
    """A governed prompt nobody calls. The one detector whose finding is a cleanup.

    Both windows must be empty, so a prompt that was quiet yesterday and busy
    today does not produce a finding on the strength of one silent day.
    """
    if released_at is None:
        return None
    if now - released_at < UNUSED_AFTER:
        return None
    if windows.current.requests or windows.prior.requests:
        return None

    return Anomaly(
        detector_id=DetectorId.RELEASED_BUT_UNUSED,
        params={"days_since_release": (now - released_at).days},
    )


#: The nine that need nothing but a window pair, in the order a card ranks them
#: when the triage model is unavailable. `fallback_rising` leads because it is
#: the one anomaly here that means users are currently getting a worse answer.
DETECTORS: Final[tuple[Callable[[WindowPair], Anomaly | None], ...]] = (
    fallback_rising,
    caller_error_clustering,
    truncation_rising,
    pinned_share_rising,
    output_ratio_drift,
    usage_unknown_appearing,
    cost_unpriced_appearing,
    latency_tail_shift,
    chain_depth_rising,
)


def run_ledger_detectors(windows: WindowPair) -> tuple[Anomaly, ...]:
    """Every ledger detector, in ranking order. Empty is the common answer.

    **Empty is the SUCCESS condition** and the sweep writes nothing for it —
    A-162's inversion, reused from ADR-0064. A module that always found something
    would be a module whose findings mean nothing.
    """
    found = (detect(windows) for detect in DETECTORS)
    return tuple(anomaly for anomaly in found if anomaly is not None)


def profile_drift(
    declared: dict[str, str] | None, stamped: dict[str, str] | None
) -> Anomaly | None:
    """*Serving the public; approved as internal.* **ADR-0067 D-02's payoff.**

    Reads nothing from the ledger. It compares the four axes currently on
    ``registry.prompt_property`` with the copy stamped onto the released revision
    when it was created — and without that stamp the comparison has nothing on
    the right-hand side, so this detector is undetectable rather than merely
    unimplemented. That is the whole argument for D-02 having cost a migration.

    ``params`` names WHICH axes moved and in which direction, because *"the
    profile changed"* is not actionable and *"audience: internal -> public"* is.
    Note-only (``REMEDY_KIND``): a declaration is a person's to change, and a
    module that proposed an edit to one would be inferring the profile through
    the back door, which A-163 forbids.
    """
    if not declared or not stamped:
        return None

    moved = {
        axis: {"stamped": stamped.get(axis), "declared": value}
        for axis, value in declared.items()
        if stamped.get(axis) != value
    }
    if not moved:
        return None

    return Anomaly(detector_id=DetectorId.PROFILE_DRIFT, params={"axes": moved})


def probe_leak_appeared(
    current_leaked: int, prior_leaked: int, cases: int
) -> Anomaly | None:
    """The guardrail became bypassable and nothing errored (deck 6 slide 25).

    **Both runs must have COMPLETED**, which the caller enforces by passing only
    completed runs: a provider outage is not a guardrail regression, and reporting
    one as the other would make an incident look like a security finding and send
    somebody to fix the wrong thing.

    Fires on any increase rather than on a proportional one. The pre-release probe
    established that these cases were refused; a case that leaks now is a fact
    about a guardrail that used to hold, and one is enough.
    """
    if cases <= 0 or current_leaked <= prior_leaked:
        return None

    return Anomaly(
        detector_id=DetectorId.PROBE_LEAK_APPEARED,
        params={"leaked": current_leaked, "prior_leaked": prior_leaked, "cases": cases},
    )

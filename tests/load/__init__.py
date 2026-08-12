"""Load tests — CL-12's two properties, at two durations, in two files.

CL-12's claim is *"enqueuing a call record stays off the caller's response path
at p95 under 1 ms under sustained load, with no metadata dropped"*, and
``docs/modules/call-ledger.lock.yml``'s stated ``condition`` for it is **the
queue at 80% depth**. ROADMAP SC5 adds the duration: 50 rps sustained for ten
minutes. **The claim splits across this package's two files, and the split is
the decision** (D-45):

``test_enqueue_off_response_path.py`` runs **in the default suite, with no
marker and no skip**. It asserts the p95 and the zero-drop claim at the lock
file's stated 80% depth, in-process, for roughly 900 ``enqueue()`` calls. SC5
proven by a test that never executes is SC5 not proven, so the half that can run
on every commit does.

``test_fifty_rps_for_ten_minutes.py`` is ROADMAP SC5's literal condition —
thirty thousand records over ten minutes against a live broker and a live
database — and it is **marked and skipped by default** with its reason printed
in the pytest summary. A suite that takes twelve minutes is a suite nobody runs,
and a gate nobody runs has stopped gating. Run it with ``make load`` or
``PROPE_RUN_LOAD=1 uv run pytest -m load``.

**No configuration change was needed to collect this directory.**
``pyproject.toml``'s ``testpaths = ["tests"]`` already reaches it. The only
selection-affecting change either file makes is the ``load`` marker's
registration, and **no ``addopts`` key is added** — ``uv run pytest -q`` selects
exactly what it selected before this package existed, which is what
ORCHESTRATION §9's gate is literally written against.

**The three helpers below read the process-global metric registry, and every one
of them is used as a DELTA.** ``prometheus_client``'s default ``REGISTRY`` is
per process and the suite shares one, so a test asserting an absolute count
passes alone and fails after its neighbour — the worst failure shape a suite can
have. There is deliberately no autouse registry-reset fixture anywhere in this
repository: it would hide every counter's cross-test behaviour, which is the one
thing these counters exist to make visible.

**``counter_value`` is a third copy** — ``tests/broker/_helpers.py:99`` and
``tests/integration/test_write_path.py:140`` carry the other two — and the copy
is deliberate rather than lazy. ``tests/load/test_enqueue_off_response_path.py``
claims to ask for no broker at all; importing a helper module that imports
``aio_pika``, the drain and the fallback to borrow four lines would make that
claim false at import time, for no benefit.
"""

from collections.abc import Sequence

from prometheus_client import REGISTRY
from prometheus_client.utils import floatToGoString


def counter_value(name: str, labels: dict[str, str] | None = None) -> float:
    """One metric's current value, or ``0.0`` if nothing has touched it.

    ``0.0`` and not ``None``: ``REGISTRY.get_sample_value`` answers ``None`` for
    a metric no code has yet incremented, and a "must stay 0" counter read
    before its first increment is the case that matters most here.
    """
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def bucket_edge(buckets: Sequence[float], target: float) -> float:
    """The histogram edge equal to ``target``, taken FROM the declared tuple.

    Two things this buys, and the second is the reason it exists as a function
    rather than as a literal at each assertion site.

    It returns **the tuple's own float object**, so the ``le`` label string a
    caller renders from it is byte-identical to the one ``prometheus_client``
    rendered when it built the histogram. A hand-written ``"0.001"`` would agree
    today and stop agreeing the moment somebody writes ``1e-3``.

    And it **fails loudly when the edge is gone**. ``histogram_quantile``
    interpolates linearly *inside* the bucket that holds the quantile, so a
    target that is not an edge can only ever be answered to that bucket's width
    — which is precisely why ``observability.py`` chose these edges around the
    numbers this project asserts on. A lookup that quietly returned the next
    edge up would turn "the target moved into a bucket's interior" into a test
    that still passes against a metric that can no longer fail its own target.
    """
    for edge in buckets:
        if edge == target:
            return edge
    raise AssertionError(
        f"{target} is not one of {tuple(buckets)!r}. This assertion needs the target to be a "
        "bucket EDGE: histogram_quantile interpolates inside the bucket holding the quantile, so "
        "a target in a bucket's interior can only be answered to that bucket's width. Restore the "
        "edge in prope.observability rather than moving this assertion to the nearest one"
    )


def histogram_totals(
    name: str,
    edge: float,
    labels: dict[str, str] | None = None,
) -> tuple[float, float]:
    """``(observations at or below ``edge``, observations in total)`` for one histogram.

    ``name`` is the metric's declared name; ``prometheus_client`` renders a
    histogram as ``<name>_bucket`` (cumulative, one series per ``le``),
    ``<name>_sum``, ``<name>_count`` and ``<name>_created``, so both reads below
    add their own suffix rather than taking a rendered name from a caller.

    The buckets are **cumulative**, which is what makes the first return value
    answer "how many observations were at or below this edge" with one read
    instead of a sum across edges — and what makes ``at_or_below / total`` a
    quantile check rather than a histogram reconstruction.
    """
    selector = dict(labels or {})
    at_or_below = REGISTRY.get_sample_value(
        f"{name}_bucket", {**selector, "le": floatToGoString(edge)}
    )
    total = REGISTRY.get_sample_value(f"{name}_count", selector)
    return at_or_below or 0.0, total or 0.0

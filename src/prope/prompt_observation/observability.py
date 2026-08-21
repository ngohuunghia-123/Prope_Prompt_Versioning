"""The three metrics `prompt-observation.lock.yml` declares. All defined at import.

D-40's rule, for this module's own version of the reason: ``write_failed_total``
is what makes A-155's *best-effort* write honest rather than silent, and
``REGISTRY.get_sample_value`` answers ``None`` — not ``0.0`` — for a metric
nothing has touched. A counter that is supposed to sit at zero and is defined
lazily is indistinguishable from one that was never wired up.

**The lock lists a fourth, ``prope_observed_call_total``, and it is not here.**
It counts a decision the GATEWAY makes — *this call could not be resolved, so it
was forwarded* — and it is declared where that decision is taken, as
``prope_gateway_observed_call_total`` in ``prope.gateway.observability``.
Declaring it twice under two names would give Grafana two half-counts of one
event. The lock listed it because the forwarded path is this module's reason for
existing, which is true and is not the same as owning the counter.

**No label anywhere carries a workspace id, a namespace, a model name or a
fingerprint.** The last two are caller-supplied text and therefore unbounded by
construction, and ADR-0030 bounds label cardinality on purpose. ``groups`` is a
process-wide total for that reason: per-workspace counts are a query against
``observation.observation``, which is indexed for it, and never a metric
dimension.
"""

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "WRITE_BUCKETS",
    "groups",
    "write_duration_seconds",
    "write_failed_total",
]

#: Shares the gateway's ``ENQUEUE_BUCKETS`` edges rather than importing them,
#: because it shares that span's budget and its background task but not its
#: module. Copied deliberately: an import here would be a second edge from
#: prompt-observation into the gateway for four floats.
WRITE_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf"))

#: The post-flush span. Excluded from the gateway's added-latency figure by
#: construction rather than by subtraction — it runs after the response is gone.
write_duration_seconds = Histogram(
    "prope_observation_write_duration_seconds",
    "Time to record one observation, after the caller's response was flushed.",
    buckets=WRITE_BUCKETS,
)

#: A lost observation costs a counter; a lost call record costs money. That
#: asymmetry is why the write is abandoned on failure and never retried, and this
#: is the counter it costs.
write_failed_total = Counter(
    "prope_observation_write_failed_total",
    "Observations abandoned after the response was flushed.",
)

#: How much ungoverned prompt surface Prope is holding, process-wide. The number
#: the ninety-day test is scored on is *N discovered, M governed*, and this is
#: the N — refreshed by whatever reads the table, not by this module guessing.
groups = Gauge(
    "prope_observation_groups",
    "Distinct fingerprint groups held across all workspaces.",
)

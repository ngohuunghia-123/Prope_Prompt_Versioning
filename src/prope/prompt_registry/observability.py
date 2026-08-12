"""The six metrics `prompt-registry.lock.yml` declares. All defined at import.

D-40's rule, and two of these are the sharpest cases in the project for it:
``unfiltered_query_total`` and the ``no_release`` line of ``resolve_miss_total``
both exist to be **zero**, and ``REGISTRY.get_sample_value`` answers ``None`` —
not ``0.0`` — for a metric nothing has touched. A "must stay 0" metric defined
lazily is indistinguishable from one that was never wired, and
``RegistryUnfilteredQuery`` pages on it.

**``revision_created_total`` ships with NO labels, and the lock asks for one.**
Its ``observability_requirements`` block writes ``labels: workspace``.
``src/prope/observability.py`` states the project-wide rule that contradicts it,
in as many words: *"``workspace_id`` — the highest-cardinality identifier in the
system and the one most tempting to add — is deliberately never a label"*, which
is ADR-0030's bounded-cardinality requirement applied. A label carrying anything
**other** than the workspace id would be worse than none: a constant token reads
as a real dimension in Grafana and answers nothing, and no other bounded value
about a workspace exists to put there. So the counter answers *are revisions
being written* and the trail that answers *by whom, on what, and when* is
``history.history_event``, which is indexed for exactly that question. Raised as
``docs/brainstorm/open_questions/OQ-141.md`` rather than resolved by editing the
lock or by shipping a label that lies.
"""

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "RESOLVE_BUCKETS",
    "SEARCH_BUCKETS",
    "resolve_duration_seconds",
    "unapproved_pointer_rows",
    "resolve_miss_total",
    "revision_conflict_total",
    "revision_created_total",
    "search_duration_seconds",
    "unfiltered_query_total",
]

#: Bucket edges, not a shape somebody liked. ``histogram_quantile`` interpolates
#: linearly INSIDE the bucket holding the quantile, so the number this project
#: asserts on must be an edge: **0.01** is the lock's ``resolve p95 < 10 ms``, and
#: ``RegistryResolveLatencyHigh`` reads the same figure. ``prometheus_client``'s
#: default set starts at 0.005 and jumps to 0.01, which would answer the target to
#: the width of one bucket and never fail it.
RESOLVE_BUCKETS = (0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, float("inf"))

#: **0.5** is the lock's ``search p95 < 500 ms``, on the same rule.
SEARCH_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, float("inf"))

resolve_duration_seconds = Histogram(
    "prope_registry_resolve_duration_seconds",
    "Wall time for one model-name resolution, by outcome.",
    labelnames=("outcome",),
    buckets=RESOLVE_BUCKETS,
)

resolve_miss_total = Counter(
    "prope_registry_resolve_miss_total",
    "Resolutions that returned no binding, separated into the two cases that are "
    "one 404 to the caller: an unknown model name, and a known one with nothing released.",
    labelnames=("reason",),
)

search_duration_seconds = Histogram(
    "prope_registry_search_duration_seconds",
    "Wall time for one list-and-search query, by whether a keyword was supplied.",
    labelnames=("keyword",),
    buckets=SEARCH_BUCKETS,
)

revision_created_total = Counter(
    "prope_registry_revision_created_total",
    "Revisions written. Unlabelled: see this module's docstring and OQ-141.",
)

revision_conflict_total = Counter(
    "prope_registry_revision_conflict_total",
    "Concurrent revision-number collisions arbitrated by uq_revision_prompt_id.",
)

unfiltered_query_total = Counter(
    "prope_registry_unfiltered_query_total",
    "Reads issued through the named unsafe path that skips INT-002's visibility "
    "filter. Must stay 0; RegistryUnfilteredQuery pages on any movement.",
)

#: The seventh metric, and the lock's list names six. It exists because the lock
#: also declares ``RegistryUnapprovedPointer``, whose condition it states as a
#: SQL query — and Prometheus cannot run SQL, so an alert written against nothing
#: is an alert that is true on paper. ``prope.prompt_registry.reconciliation``
#: carries the whole argument for what sets it, why the sweep enumerates tenants
#: rather than reading across them, and what its once-per-startup window does and
#: does not cover.
#:
#: A ``Gauge`` and not a ``Counter``: the quantity is *how many rows are wrong
#: right now*, and a counter would make a fixed problem look permanent.
unapproved_pointer_rows = Gauge(
    "prope_registry_unapproved_pointer_rows",
    "Released pointers naming a revision whose status is not Approved, across "
    "every workspace, as of the last reconciliation. Must stay 0.",
)

"""The metrics `gateway.lock.yml` declares. All defined at import (D-40)."""

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "ADDED_LATENCY_BUCKETS",
    "CHUNK_RELAY_BUCKETS",
    "ENQUEUE_BUCKETS",
    "REQUEST_BUCKETS",
    "RESOLVE_BUCKETS",
    "added_latency_seconds",
    "admission_refused_total",
    "auth_failure_total",
    "call_total",
    "chunk_relay_seconds",
    "enqueue_duration_seconds",
    "fallback_total",
    "in_flight",
    "oversize_request_total",
    "pinned_call_total",
    "record_missing_version_id_total",
    "rejected_system_message_total",
    "request_duration_seconds",
    "resolve_duration_seconds",
    "resolve_miss_total",
    "upstream_error_total",
    "usage_missing_total",
]

RESOLVE_BUCKETS = (
    0.0001,
    0.00025,
    0.0005,
    0.001,
    0.0025,
    0.005,
    0.01,
    0.015,
    0.05,
    float("inf"),
)

ADDED_LATENCY_BUCKETS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    float("inf"),
)

REQUEST_BUCKETS = (
    0.01,
    0.05,
    0.1,
    0.3,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    float("inf"),
)

ENQUEUE_BUCKETS = (
    0.00005,
    0.0001,
    0.00025,
    0.0005,
    0.00075,
    0.001,
    0.0025,
    0.005,
    0.01,
    0.05,
    float("inf"),
)

CHUNK_RELAY_BUCKETS = (
    0.0001,
    0.00025,
    0.0005,
    0.001,
    0.002,
    0.005,
    0.01,
    0.05,
    float("inf"),
)

request_duration_seconds = Histogram(
    "prope_gateway_request_duration_seconds",
    "Wall time for a whole gateway request, upstream call included.",
    labelnames=("route", "streaming", "outcome"),
    buckets=REQUEST_BUCKETS,
)

added_latency_seconds = Histogram(
    "prope_gateway_added_latency_seconds",
    "Arrival to dispatch plus upstream completion to flush. Excludes the upstream call.",
    buckets=ADDED_LATENCY_BUCKETS,
)

resolve_duration_seconds = Histogram(
    "prope_gateway_resolve_duration_seconds",
    "Time to turn a model name into a revision binding, by whether the cache held it.",
    labelnames=("cache",),
    buckets=RESOLVE_BUCKETS,
)

resolve_miss_total = Counter(
    "prope_gateway_resolve_miss_total",
    "Requests that produced no binding, by which kind of miss it was.",
    labelnames=("reason",),
)

fallback_total = Counter(
    "prope_gateway_fallback_total",
    "Fallback answers served, by the upstream failure that reached for one.",
    labelnames=("reason",),
)

upstream_error_total = Counter(
    "prope_gateway_upstream_error_total",
    "Upstream failures, separated by whether a byte had already reached the caller.",
    labelnames=("stage",),
)

call_total = Counter(
    "prope_gateway_call_total",
    "Calls served, by the outcome written to the call record.",
    labelnames=("outcome",),
)

pinned_call_total = Counter(
    "prope_gateway_pinned_call_total",
    "Calls served from a pinned revision, by prompt. The restore-blindness signal.",
    labelnames=("prompt",),
)

rejected_system_message_total = Counter(
    "prope_gateway_rejected_system_message_total",
    "Requests refused for carrying a caller-supplied system message (ADR-0011).",
)

usage_missing_total = Counter(
    "prope_gateway_usage_missing_total",
    "Served calls whose provider returned no usage object. Must stay 0.",
)

record_missing_version_id_total = Counter(
    "prope_gateway_record_missing_version_id_total",
    "Call records enqueued with no version id. Must stay 0.",
)

enqueue_duration_seconds = Histogram(
    "prope_gateway_enqueue_duration_seconds",
    "The post-flush handoff of a call record to call-ledger.",
    buckets=ENQUEUE_BUCKETS,
)

auth_failure_total = Counter(
    "prope_gateway_auth_failure_total",
    "Requests refused before a consumer key was identified.",
)

oversize_request_total = Counter(
    "prope_gateway_oversize_request_total",
    "Requests refused for a composed message set above the cap (A-148).",
)

admission_refused_total = Counter(
    "prope_gateway_admission_refused_total",
    "Requests refused at the per-key in-flight cap, by a bucket of the key id (A-143).",
    labelnames=("key_id_bucket",),
)

in_flight = Gauge(
    "prope_gateway_inflight",
    "Chat-completion requests currently in flight in this process.",
)

chunk_relay_seconds = Histogram(
    "prope_gateway_chunk_relay_seconds",
    "Per-chunk relay overhead on a streaming response, accumulation included.",
    buckets=CHUNK_RELAY_BUCKETS,
)

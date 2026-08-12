"""The fourteen metrics `provider-access.lock.yml` declares. All defined at import."""

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "admission_wait_seconds",
    "catalogue_refresh_total",
    "credential_decrypt_seconds",
    "credential_rejected_total",
    "dispatch_duration_seconds",
    "dispatch_overhead_seconds",
    "dispatch_total",
    "error_total",
    "kek_unavailable",
    "model_unavailable_total",
    "shed_total",
    "upstream_duration_seconds",
    "usage_missing_total",
    "verification_total",
]

DISPATCH_DURATION_BUCKETS = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    30.0,
    60.0,
    float("inf"),
)

OVERHEAD_BUCKETS = (
    0.0005,
    0.001,
    0.002,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    float("inf"),
)

DECRYPT_BUCKETS = (0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.05, float("inf"))

ADMISSION_BUCKETS = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.1, 1.0, float("inf"))

dispatch_duration_seconds = Histogram(
    "prope_provider_access_dispatch_duration_seconds",
    "Wall time for a whole dispatch, upstream call included.",
    labelnames=("priority", "streaming", "outcome"),
    buckets=DISPATCH_DURATION_BUCKETS,
)

dispatch_overhead_seconds = Histogram(
    "prope_provider_access_dispatch_overhead_seconds",
    "Dispatch wall time minus the measured upstream call.",
    labelnames=("priority", "streaming"),
    buckets=OVERHEAD_BUCKETS,
)

upstream_duration_seconds = Histogram(
    "prope_provider_access_upstream_duration_seconds",
    "Wall time the provider itself took, by configuration and upstream model.",
    labelnames=("provider_config_id", "upstream_model"),
    buckets=DISPATCH_DURATION_BUCKETS,
)

dispatch_total = Counter(
    "prope_provider_access_dispatch_total",
    "Dispatches issued, by priority and outcome.",
    labelnames=("priority", "outcome"),
)

error_total = Counter(
    "prope_provider_access_error_total",
    "Typed dispatch failures. The four facts ADR-0017 keeps separate are four labels.",
    labelnames=("class", "origin", "fallback_eligible", "retryable"),
)

admission_wait_seconds = Histogram(
    "prope_provider_access_admission_wait_seconds",
    "Time spent waiting for an admission slot, by priority.",
    labelnames=("priority",),
    buckets=ADMISSION_BUCKETS,
)

shed_total = Counter(
    "prope_provider_access_shed_total",
    "Dispatches refused by Prope's own admission gate, by priority and reason.",
    labelnames=("priority", "reason"),
)

usage_missing_total = Counter(
    "prope_provider_access_usage_missing_total",
    "Completed dispatches that carried no usage object. Must stay 0.",
)

credential_decrypt_seconds = Histogram(
    "prope_provider_access_credential_decrypt_seconds",
    "Wall time to produce a usable credential, by whether the process cache held it.",
    labelnames=("cache",),
    buckets=DECRYPT_BUCKETS,
)

credential_rejected_total = Counter(
    "prope_provider_access_credential_rejected_total",
    "Upstream refusals of the stored credential, by configuration.",
    labelnames=("provider_config_id",),
)

kek_unavailable = Gauge(
    "prope_provider_access_kek_unavailable",
    "1 when no key-encryption key is loadable, so no credential can be decrypted.",
)

verification_total = Counter(
    "prope_provider_access_verification_total",
    "Verification probes, by result and by the reason a failing one gave.",
    labelnames=("result", "reason"),
)

catalogue_refresh_total = Counter(
    "prope_provider_access_catalogue_refresh_total",
    "Model catalogue refreshes, by result.",
    labelnames=("result",),
)

model_unavailable_total = Counter(
    "prope_provider_access_model_unavailable_total",
    "Dispatches naming a model the provider no longer serves.",
    labelnames=("provider_config_id", "upstream_model"),
)

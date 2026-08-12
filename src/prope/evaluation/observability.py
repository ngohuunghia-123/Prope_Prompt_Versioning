from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "CASE_DURATION_BUCKETS",
    "COST_RATIO_BUCKETS",
    "RUN_DURATION_BUCKETS",
    "baseline_reused_total",
    "case_duration_seconds",
    "case_error_total",
    "case_flip_total",
    "cost_delta_ratio",
    "modality_mismatch_total",
    "run_duration_seconds",
    "run_interrupted_total",
    "run_queue_depth",
    "run_total",
    "unpriced_run_total",
]

RUN_DURATION_BUCKETS = (1.0, 5.0, 15.0, 30.0, 60.0, 90.0, 120.0, 300.0, 600.0, float("inf"))

CASE_DURATION_BUCKETS = (0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf"))

COST_RATIO_BUCKETS = (0.5, 0.8, 0.95, 1.0, 1.05, 1.2, 1.5, 2.0, 5.0, float("inf"))

run_duration_seconds = Histogram(
    "prope_evaluation_run_duration_seconds",
    "Wall time for one suite run, from claim to terminal status.",
    labelnames=("role", "status"),
    buckets=RUN_DURATION_BUCKETS,
)

case_duration_seconds = Histogram(
    "prope_evaluation_case_duration_seconds",
    "Wall time for one eval case, dispatch and assertion evaluation together.",
    buckets=CASE_DURATION_BUCKETS,
)

run_total = Counter(
    "prope_evaluation_run_total",
    "Runs that reached a terminal status, by which one.",
    labelnames=("status",),
)

case_error_total = Counter(
    "prope_evaluation_case_error_total",
    "Cases that ended in a dispatch or assertion-machinery failure. Never an "
    "assertion failure, which is a fail and not an error (A-057).",
    labelnames=("error_code",),
)

case_flip_total = Counter(
    "prope_evaluation_case_flip_total",
    "Cases whose outcome changed between two runs of the same revision on the "
    "same suite version. Sampling noise, surfaced rather than smoothed.",
)

baseline_reused_total = Counter(
    "prope_evaluation_baseline_reused_total",
    "Baseline pairings, separated into the one that cost nothing and the one "
    "that dispatched a fresh run (ADR-0004).",
    labelnames=("decision",),
)

run_interrupted_total = Counter(
    "prope_evaluation_run_interrupted_total",
    "Runs the restart sweeper reaped after five minutes with no case progress.",
)

cost_delta_ratio = Histogram(
    "prope_evaluation_cost_delta_ratio",
    "Candidate cost over baseline cost, per suite. The warning threshold reads "
    "this series; nothing about cost blocks a release.",
    buckets=COST_RATIO_BUCKETS,
)

run_queue_depth = Gauge(
    "prope_evaluation_run_queue_depth",
    "Runs sitting in queued behind the per-workspace admission bound (A-063).",
)

unpriced_run_total = Counter(
    "prope_evaluation_unpriced_run_total",
    "Runs that completed with no money column, by why. The eleventh metric "
    "where the lock declares ten: EvalPricingStalled is declared as an alert on "
    "completed runs whose priced_at is still NULL, and no metric in that list "
    "carries the condition, so an alert written against it would be true only "
    "on paper.",
    labelnames=("reason",),
)

modality_mismatch_total = Counter(
    "prope_evaluation_modality_mismatch_total",
    "Runs refused because the suite's declared modality did not match the shape "
    "the target returned. Must stay 0.",
)

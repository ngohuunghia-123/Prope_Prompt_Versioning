from prometheus_client import Counter, Gauge, Histogram

append_rejected_total = Counter(
    "prope_property_history_append_rejected_total",
    "Appends refused by the vocabulary or the payload allow-list, by reason. Must stay 0.",
    labelnames=("reason",),
)

APPEND_DURATION_BUCKETS = (
    0.0005,
    0.001,
    0.002,
    0.003,
    0.005,
    0.01,
    0.025,
    0.05,
    float("inf"),
)

append_total = Counter(
    "prope_property_history_append_total",
    "Events appended, by action and by the module that wrote them.",
    labelnames=("action", "writing_module"),
)

append_duration_seconds = Histogram(
    "prope_property_history_append_duration_seconds",
    "Wall time inside append(), as a share of the caller's transaction.",
    buckets=APPEND_DURATION_BUCKETS,
)

READ_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    1.0,
    float("inf"),
)

read_duration_seconds = Histogram(
    "prope_property_history_read_duration_seconds",
    "Wall time inside read(), by scope kind.",
    labelnames=("scope_kind",),
    buckets=READ_DURATION_BUCKETS,
)

EVENTS_RETURNED_BUCKETS = (0, 1, 5, 10, 25, 50, 100, 150, 200)

events_returned = Histogram(
    "prope_property_history_events_returned",
    "Events returned per read() call.",
    buckets=EVENTS_RETURNED_BUCKETS,
)

rows_total = Gauge(
    "prope_property_history_rows_total",
    "Total rows in history.history_event. Unlabelled (OQ-030); unset until a workspace enumerator exists (OQ-037).",
)

null_scope_prompt_total = Counter(
    "prope_property_history_null_scope_prompt_total",
    "Prompt-scoped events appended with a null scope_prompt_id, by action. Must stay 0.",
    labelnames=("action",),
)

write_failed_total = Counter(
    "prope_property_history_write_failed_total",
    "append() INSERTs that raised for a reason other than a closed rejection. Must stay 0.",
)

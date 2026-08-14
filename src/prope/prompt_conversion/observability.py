"""Metrics for conversion, independent from prompt-search health.

Six series, and the split between them and Langfuse is deliberate. Prometheus
holds what an ALERT RULE is written against: closed label sets, no identifiers,
survives a Langfuse outage, scraped by the same job as everything else in
`deploy/prometheus`. Langfuse holds the per-request span tree, the token usage
against a managed prompt version, and the per-trace scores — the things whose
whole value is that they are high-cardinality and therefore must never be a
metric label (ADR-0030's cardinality clause; `workspace_id` is not here for the
same reason it is not in `prope.observability`).

The three series added beyond attempts/duration/breaker exist because an LLM in
a request path has two failure modes ordinary metrics cannot see: it can get
expensive without erroring, and it can get WORSE without erroring. `tokens` and
`cost_usd` cover the first, `coverage_ratio` covers the second.
"""

from prometheus_client import Counter, Gauge, Histogram

conversion_total = Counter(
    "prope_prompt_conversion_total",
    "Prompt conversion attempts by outcome.",
    ("outcome",),
)
conversion_duration_seconds = Histogram(
    "prope_prompt_conversion_duration_seconds",
    "Duration of app-agent prompt conversions.",
)
agent_circuit_open = Gauge(
    "prope_prompt_conversion_agent_circuit_open",
    "Whether the prompt conversion App Agent circuit is open.",
)
conversion_repair_total = Counter(
    "prope_prompt_conversion_repair_total",
    "Prompt conversions that required the bounded repair attempt.",
)

conversion_prompt_fallback_total = Counter(
    "prope_prompt_conversion_prompt_fallback_total",
    "Prompt conversions using the local system-prompt fallback.",
)

#: Labelled by DIRECTION and by nothing else. Output tokens cost 4-6x input at
#: every provider in the 2026 price table, so a single `tokens_total` would
#: average away the only half of the number that moves a bill. `model` is not a
#: label: `APP_AGENT_MODEL` is one app-owned value per deployment, so it would
#: be a constant label that stops being constant exactly once — during a model
#: migration — and breaks every rate() that spans the change.
conversion_tokens_total = Counter(
    "prope_prompt_conversion_tokens_total",
    "Tokens consumed by app-agent prompt conversions, by direction.",
    ("direction",),
)

#: A counter in dollars, not a gauge. Cost is cumulative and the question an
#: operator asks is "how much today", which is `increase(...[1d])` over a
#: counter and is not answerable from a gauge at all. The number comes from the
#: provider's own usage counts times `dspy_program.PRICE_*_PER_MTOK`, so it is
#: an estimate that tracks the bill rather than the bill itself; the daily-budget
#: alert is written against it because waiting for the invoice is the failure
#: mode it exists to prevent.
conversion_cost_usd_total = Counter(
    "prope_prompt_conversion_cost_usd_total",
    "Estimated USD spent on app-agent prompt conversions, from provider token counts.",
)

#: The fourth pillar, as one number per successful conversion. See
#: `domain.content_coverage` for what it measures and why it is not an
#: LLM-as-judge. Buckets are dense either side of 1.0 because the whole
#: population should sit there: the alertable event is the left tail appearing
#: at all, not the shape of the distribution.
conversion_coverage_ratio = Histogram(
    "prope_prompt_conversion_coverage_ratio",
    "Classified characters over source characters for successful conversions.",
    buckets=(0.25, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0, 1.05, 1.2, 1.5, float("inf")),
)

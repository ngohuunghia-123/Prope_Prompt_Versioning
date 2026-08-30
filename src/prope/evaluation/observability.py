from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "CASE_DURATION_BUCKETS",
    "COST_RATIO_BUCKETS",
    "RUN_DURATION_BUCKETS",
    "advisor_circuit_open",
    "advisor_cost_usd_total",
    "advisor_suggestions_dropped_total",
    "advisor_total",
    "baseline_reused_total",
    "case_duration_seconds",
    "case_error_total",
    "case_flip_total",
    "cost_delta_ratio",
    "llm_cache_cost_saved_usd_total",
    "llm_cache_errors_total",
    "llm_cache_put_total",
    "llm_cache_total",
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


#: --- the eval-case drafter, step 4b ------------------------------------------
#:
#: Separate from the run metrics above because they answer a different question.
#: A run's numbers are about a prompt; these are about the drafting agent, and
#: an outage in it must never read as a prompt getting worse.

drafter_total = Counter(
    "prope_evaluation_drafter_total",
    "Drafting attempts by how they ended. `refused` is the circuit breaker "
    "declining to call, which is a healthy state and not an error.",
    labelnames=("outcome",),
)

drafter_cases_dropped_total = Counter(
    "prope_evaluation_drafter_cases_dropped_total",
    "Drafted cases and assertions discarded before the dataset was written, by "
    "why. A model that invents an assertion type or an uncompilable regex is "
    "expected; silently keeping it is what would not be.",
    labelnames=("reason",),
)

drafter_cost_usd_total = Counter(
    "prope_evaluation_drafter_cost_usd_total",
    "App-agent spend on drafting, from the provider's own token counts. Not the "
    "workspace's provider and not `ledger.call_record` — this is Prope's own "
    "bill for a convenience feature, and conflating the two would put an "
    "internal cost into a customer's cost delta.",
)

drafter_circuit_open = Gauge(
    "prope_evaluation_drafter_circuit_open",
    "1 while the drafter's breaker is open. Drafting is unavailable; nothing "
    "else in evaluation is affected.",
)


#: --- the dataset suggester, the advisor's model-backed half -------------------
#:
#: Same split as the drafter's block above: these answer a question about an
#: advice feature, and an outage in it must never read as a prompt or a run
#: getting worse.

advisor_total = Counter(
    "prope_evaluation_advisor_total",
    "Dataset-suggestion attempts by how they ended. `empty` is a successful "
    "call that judged nothing truly relevant — an answer, not a failure; "
    "`refused` is the breaker declining to call, which is a healthy state.",
    labelnames=("outcome",),
)

advisor_suggestions_dropped_total = Counter(
    "prope_evaluation_advisor_suggestions_dropped_total",
    "Model proposals discarded before a person saw them, by why. A model that "
    "names an id the catalogue never showed is expected; showing it one is "
    "what would not be.",
    labelnames=("reason",),
)

advisor_cost_usd_total = Counter(
    "prope_evaluation_advisor_cost_usd_total",
    "App-agent spend on dataset suggestions, from the provider's own token "
    "counts. Prope's own bill for a convenience feature, never "
    "`ledger.call_record`.",
)

advisor_circuit_open = Gauge(
    "prope_evaluation_advisor_circuit_open",
    "1 while the suggester's breaker is open. Suggesting is unavailable; "
    "nothing else in evaluation is affected.",
)


#: --- the App-Agent LLM call cache (design pack `docs/agent-design/cache/`) -----
#:
#: The cache is a request-path optimization, so its observability is counters,
#: not traces (06-D1). Labels are closed enums: `feature` names the DSPy program
#: (`suggest_datasets` today; the set is extended only in the commit that wires
#: a caller), `result` and `op` are enumerated here. No workspace, prompt, user
#: or model-name labels (ADR-0030, 06-D6).

#: How every read ended. `hit` served a row; `miss` called the model; a
#: poisoned row (stored but failing the gate on read) and a degraded read are
#: counted apart so a dashboard can tell a healthy miss from a broken cache
#: (01-D6).
llm_cache_total = Counter(
    "prope_evaluation_llm_cache_total",
    "App-Agent LLM cache reads, by feature and how they ended. `hit` served a "
    "row; `miss` called the model; `miss_stale` dropped a poisoned row; "
    "`miss_degraded` fell through a failed read.",
    labelnames=("feature", "result"),
)

#: Whether a miss's fresh answer was stored. `write_failed` is the
#: fault-isolation proof: the answer was still returned, and this counter is
#: what makes that visible (06-D7).
llm_cache_put_total = Counter(
    "prope_evaluation_llm_cache_put_total",
    "App-Agent LLM cache writes, by feature and how they ended.",
    labelnames=("feature", "result"),
)

#: Cache read/write errors. A sustained rate is a bug in the seam, not a
#: provider outage — the only cache condition worth a ticket (06-D10).
llm_cache_errors_total = Counter(
    "prope_evaluation_llm_cache_errors_total",
    "App-Agent LLM cache read/write failures, by feature and operation.",
    labelnames=("feature", "op"),
)

#: PROPE's meter, never a workspace cost delta. A hit's avoided spend, computed
#: from the stored token counts of the call that originally produced the row ×
#: the existing price table (06-D11/D12). The same rule every other app-agent
#: cost metric carries: not a `ledger.call_record`, never inside a delta.
llm_cache_cost_saved_usd_total = Counter(
    "prope_evaluation_llm_cache_cost_saved_usd_total",
    "US dollars Prope did not spend because an LLM cache read served a row, by "
    "feature. From stored token counts, never an estimate.",
    labelnames=("feature",),
)

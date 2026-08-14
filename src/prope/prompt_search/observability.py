"""Observability: metrics and structured logging for prompt-search (ADR-0030, A-046).

Search and indexing:
  - prompt_search_quick_duration_seconds     histogram, result_count_bucket
  - prompt_search_ai_duration_seconds        histogram, result_count_bucket + cache_hit
  - prompt_search_index_triggered_total      counter, prompt_id + workspace_id
  - prompt_search_index_completed_total      counter, workspace_id + with_dup_warning
  - prompt_search_index_failed_total         counter, workspace_id + reason
  - prompt_search_embedding_cache_hits_total / _misses_total
  - prompt_search_agent_circuit_open         gauge

The extraction agent (added with the DSPy/Langfuse rework):
  - prompt_search_extraction_total                    counter, outcome
  - prompt_search_extraction_duration_seconds         histogram
  - prompt_search_extraction_tokens_total             counter, direction
  - prompt_search_extraction_cost_usd_total           counter
  - prompt_search_extraction_prompt_fallback_total    counter
  - prompt_search_extraction_body_truncated_total     counter
  - prompt_search_extraction_quality                  histogram

**A cardinality debt is recorded here rather than silently paid off.**
`prope/observability.py` states the project rule — every label has a CLOSED set
of values fixed in source, and ``workspace_id``, the highest-cardinality
identifier in the system, is deliberately never a label. The three
``index_*_total`` counters break it: they carry ``workspace_id``, and
``index_triggered_total`` also carries ``prompt_id``, which is unbounded — one
Prometheus time series per prompt ever indexed, retained for the life of the
series. They are written that way because
``docs/modules/prompt-search.lock.yml``'s ``observability_requirements`` block
declares those exact labels, so the code and its spec agree and the spec is what
disagrees with ADR-0030. Changing it is a lock-file amendment and breaks any
dashboard already reading the labels, so it is raised, not absorbed. **Every
metric added below has a closed label set**; the fix for the older three is a
``with_dup_warning``/``reason``-only shape with the identifiers moved to the log
line, where the allow-list already admits them.

Log fields (A-046):
  - actor_id, workspace_id, prompt_id, version_id, job_id, action, outcome, duration_ms
  - Never logged: prompt body, extracted metadata content. Keywords and topics
    are derived FROM the body and can carry its sensitive terms, so they are
    stored and returned but counted, never printed.
"""

from prometheus_client import Counter, Gauge, Histogram

#: Duration histogram buckets for quick search (p95 < 200ms target)
QUICK_SEARCH_BUCKETS = (0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 1.0)

#: Duration histogram buckets for AI search (p95 < 1000ms target)
AI_SEARCH_BUCKETS = (0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0, 10.0)

#: Quick search: keyword match across all prompts
quick_duration_seconds = Histogram(
    "prompt_search_quick_duration_seconds",
    "Quick (keyword) search latency in seconds",
    labelnames=("result_count_bucket",),
    buckets=QUICK_SEARCH_BUCKETS,
)

#: AI search: semantic similarity over indexed prompts
ai_duration_seconds = Histogram(
    "prompt_search_ai_duration_seconds",
    "AI (semantic) search latency in seconds",
    labelnames=("result_count_bucket", "cache_hit"),
    buckets=AI_SEARCH_BUCKETS,
)

#: Index triggered: labels for tracking
index_triggered_total = Counter(
    "prompt_search_index_triggered_total",
    "Index operations triggered",
    labelnames=("prompt_id", "workspace_id"),
)

#: Index completed: labels for tracking
index_completed_total = Counter(
    "prompt_search_index_completed_total",
    "Index operations completed",
    labelnames=("workspace_id", "with_dup_warning"),
)

#: Index failed: labels for tracking
index_failed_total = Counter(
    "prompt_search_index_failed_total",
    "Index operations failed",
    labelnames=("workspace_id", "reason"),
)

#: Embedding cache hits
embedding_cache_hits_total = Counter(
    "prompt_search_embedding_cache_hits_total",
    "Embedding cache hits",
)

#: Embedding cache misses
embedding_cache_misses_total = Counter(
    "prompt_search_embedding_cache_misses_total",
    "Embedding cache misses",
)

agent_circuit_open = Gauge(
    "prompt_search_agent_circuit_open",
    "Whether the App Agent circuit breaker is currently open",
)

# ---------------------------------------------------------------------------
# Extraction agent (the App Agent call inside an indexing job).
#
# Every label below has a CLOSED set of values fixed in this file, per ADR-0030
# and the rule stated in `prope/observability.py`: no `workspace_id`, no
# `prompt_id`, no model-supplied string ever becomes a label. The three counters
# above this block predate that rule and are discussed in the module docstring.
# ---------------------------------------------------------------------------

#: p95 target is 5,000 ms (the lock file's "index extraction time"), so the
#: buckets straddle it rather than trailing off at 1 s.
EXTRACTION_BUCKETS = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 30.0, 60.0)

#: outcome = success | invalid_output | unavailable. Mirrors
#: `prompt_search_index_failed_total{reason}` one layer down: that counter says
#: an indexing JOB failed, this one says the agent CALL inside it did, and the
#: gap between the two is embedding and database trouble.
extraction_total = Counter(
    "prompt_search_extraction_total",
    "Metadata extraction agent calls by outcome",
    labelnames=("outcome",),
)

extraction_duration_seconds = Histogram(
    "prompt_search_extraction_duration_seconds",
    "Metadata extraction agent latency in seconds",
    buckets=EXTRACTION_BUCKETS,
)

#: direction = input | output. Two series, not one, because output tokens cost
#: 4-6x input at every provider and a single total hides which one moved.
extraction_tokens_total = Counter(
    "prompt_search_extraction_tokens_total",
    "Tokens consumed by the metadata extraction agent",
    labelnames=("direction",),
)

#: Priced from the provider's own usage numbers at the call site
#: (`app_agent.dspy_runtime.cost_usd`). Indexing is the one place in Prope that
#: spends the app's own money on a user action, and the lock file's first risk is
#: that cost accumulating unnoticed.
extraction_cost_usd_total = Counter(
    "prompt_search_extraction_cost_usd_total",
    "Cumulative USD spent on metadata extraction",
)

#: Rising means the Langfuse `production` label stopped resolving and every
#: extraction is silently running the in-code fallback instruction.
extraction_prompt_fallback_total = Counter(
    "prompt_search_extraction_prompt_fallback_total",
    "Extractions that ran on the in-code fallback instruction",
)

#: The body the agent saw was cut at `dspy_program.BODY_CHARACTER_LIMIT`. Not an
#: error — long prompts are legitimate — but it means the tail of the prompt was
#: never indexed, which is exactly the invisible quality loss the previous
#: `body[:4000]` slice produced with no way to notice it.
extraction_body_truncated_total = Counter(
    "prompt_search_extraction_body_truncated_total",
    "Extractions where the prompt body was truncated before the agent saw it",
)

#: The deterministic quality score from `agent/evaluation.py`, recorded on every
#: live extraction. This is the fourth observability pillar — continuous eval —
#: and the reason it can run in production is that it needs no judge model: it
#: checks counts, shapes and language coverage, so it costs a few microseconds
#: and cannot itself drift.
extraction_quality = Histogram(
    "prompt_search_extraction_quality",
    "Deterministic quality score of an extraction, 0.0 to 1.0",
    buckets=(0.0, 0.25, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0),
)

#: Bounded because this process never restarts on a schedule. The previous
#: `set[str]` grew by one entry per polled job for the life of the container,
#: which is a slow leak in the `app` process with no upper bound and no owner.
#: A ring is correct rather than merely cheaper: the set exists to stop a
#: DOUBLE-COUNT while a client polls a finished job every second or two, and a
#: job nobody has mentioned in the last ten thousand observations is not being
#: polled any more.
_OBSERVED_JOB_MEMORY = 10_000
_observed_terminal_jobs: dict[str, None] = {}


def observe_terminal_job(
    job_id: str,
    workspace_id: str,
    status: str,
    error: str | None,
    result: dict | None,
) -> None:
    """Expose worker outcomes from the app process when the polling API observes them."""
    if job_id in _observed_terminal_jobs:
        return
    if status == "completed":
        index_completed_total.labels(
            workspace_id=workspace_id,
            with_dup_warning=str(bool((result or {}).get("nearest_neighbor_id"))).lower(),
        ).inc()
    elif status == "failed":
        reason = {
            "metadata extraction failed": "agent_error",
            "embedding generation failed": "embedding_error",
        }.get(error or "", "db_error")
        index_failed_total.labels(workspace_id=workspace_id, reason=reason).inc()
    else:
        return

    _observed_terminal_jobs[job_id] = None
    while len(_observed_terminal_jobs) > _OBSERVED_JOB_MEMORY:
        # dicts iterate in insertion order, so this drops the oldest job first.
        del _observed_terminal_jobs[next(iter(_observed_terminal_jobs))]


def result_count_bucket(count: int) -> str:
    """Bucket label for result counts."""
    if count == 0:
        return "0"
    elif count <= 10:
        return "1-10"
    elif count <= 50:
        return "11-50"
    elif count <= 100:
        return "51-100"
    else:
        return "100+"

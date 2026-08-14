"""Observability: metrics and structured logging for prompt-search (ADR-0030, A-046).

Metrics:
  - prompt_search_quick_duration_seconds: histogram for quick search latency
  - prompt_search_ai_duration_seconds: histogram for AI search latency
  - prompt_search_index_triggered_total: counter for triggered index operations
  - prompt_search_index_completed_total: counter for completed index operations
  - prompt_search_index_failed_total: counter for failed index operations
  - prompt_search_embedding_cache_hits_total: counter for embedding cache hits
  - prompt_search_embedding_cache_misses_total: counter for embedding cache misses

Log fields (A-046):
  - actor_id, workspace_id, prompt_id, version_id, job_id, action, outcome, duration_ms
  - Never logged: prompt body, extracted metadata content
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

_observed_terminal_jobs: set[str] = set()


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
    _observed_terminal_jobs.add(job_id)


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

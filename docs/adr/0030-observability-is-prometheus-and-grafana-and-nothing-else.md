# ADR-0030 — Observability is Prometheus and Grafana, and deliberately nothing else

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — cited by every module's observability requirements
**Related**: A-012, A-037, A-045, A-046, A-104, A-106, A-121, A-126, ADR-0018, ADR-0033

## Context

A-046 already fixes the conventions: *"structured JSON logs, `prope_<module>_<name>_<unit>` metrics,
bodies never logged."* That naming scheme is a Prometheus scheme, so step 1 half-answered this before
step 4 opened. A-045 adds `/healthz` and `/readyz`.

Working backwards from `00_context.md#success` shows how little of this stack is actually load-bearing.
Most Success metrics are **SQL over PostgreSQL** and need no observability product at all —
*"SQL: releases LEFT JOIN approvals, count rows with NULL approval and `break_glass = false`"*,
*"SQL over call records with NULL `version_id`"*, *"SQL over releases where `revision.status !=
'Approved'`"*. Two are human protocols: a stopwatch script and an observer checklist. A-126 already
established that the two audit-event metrics are hand-run SQL at pilot review rather than product
surfaces.

Exactly one row needs real instrumentation:

> "Latency the gateway adds on top of the upstream call | p95 < 50 ms | Instrumented span from request
> arrival to upstream dispatch, plus upstream completion to response flush; logging excluded by
> construction"

A p95 requires a histogram. On top of that sit the counters and gauges the lock files already promise:
the gateway's resolve-miss metric with its *"model name unknown"* versus *"model name known, nothing
released"* labels, A-104's ceiling-failure counter, A-106's oldest-body gauge, and A-037's body-drop
counter.

Prope is unusual in one respect that shapes this decision: **it is already a structured event store for
its own domain**. `history_event` is append-only, indexed, never deleted (A-121), and answers "who
released what, when, and why" with SQL. `call_record` answers "which calls fell back" and "which
resolved to nothing" the same way. The questions an operator most wants to ask are already answered by
the database with stronger retention guarantees than a log aggregator provides.

## Decision

**Prometheus and Grafana, two services. `prometheus-client` for metrics, `structlog` for JSON logs to
stdout, read via `docker compose logs`. No tracing, no log aggregation, no vendor.**

- Instrumentation uses `prometheus-client` directly rather than the OpenTelemetry SDK, because A-046
  already pinned Prometheus-shaped names and an OTel indirection would exist to serve a backend switch
  nobody has planned.
- **Docker's `json-file` driver is capped at `max-size: 50m, max-file: 5` per service.** Uncapped
  container logs are the most common way a small VM fills its disk, and the cap is what makes the
  "no aggregator" decision safe rather than merely cheap.
- **Label cardinality is bounded explicitly, because A-046 fixed metric *names* and never said what may
  be a *label*.** A label may be a value from a small closed set: module, outcome, failure class,
  priority class, source. `model_name` and `workspace_id` are permitted at pilot scale and reviewed if
  either grows past hundreds. A `call_id`, `version_id`, `session_id`, `consumer_key` or any per-request
  identifier is **never** a label — one such label multiplies series per request and is the realistic
  way this stack runs the host out of memory.
- The A-046 content rules bind metric labels as strictly as log lines: no prompt body, fallback answer,
  request or response body, credential, eval output, or `prope.variables` value ever appears in a label,
  a log line, or a history event. Variable *names* may be logged; values may not.
- Grafana holds one dashboard that matters for the pilot: the gateway p95 histogram beside the resolve-miss,
  fallback, body-drop and ceiling-failure counters — the four numbers that say whether the system is
  behaving.

## Alternatives rejected

**Adding Loki for log aggregation.** Rejected on the asymmetry that decides these questions. Loki's core
value is searching logs *across hosts*, and there is one host. Its secondary value — searching across
nine containers from the same Grafana time range as the metrics — is real, but the stack has seven
services, the questions worth asking are mostly answered in PostgreSQL, and **adding Loki later costs
about thirty minutes and forfeits nothing**, because logs are ephemeral by nature. This is the opposite
of ADR-0027's schema decision, where retrofitting means rewriting every query. Additionally, the
one-container variant using Docker's `loki` logging driver *replaces* the `json-file` driver, so
`docker compose logs` stops working entirely — meaning a Loki outage removes the ability to read the
logs explaining the outage. The safe variant needs Alloy or Promtail and is two containers, at which
point the trade is clearly worse than deferring.

**Distributed tracing (OpenTelemetry plus a collector).** Rejected because Prope is one process on one
host. A distributed trace with no distribution is a log line with a duration field, and the collector
is another container to justify it. This is reconsidered when ADR-0026's gateway split or ADR-0028's
worker make a request genuinely cross more than one process in a way the p95 histogram cannot explain.

**OpenTelemetry SDK exporting to a hosted backend free tier.** Rejected on data, not on capability. It
is genuinely the zero-container option with the best dashboards. But it sends telemetry off-box, and
while A-046 guarantees the *content* is safe, prompt model names and workspace identifiers would still
travel to a vendor — and OQ-013 (*"retention, read access, and PII handling must be settled before any
real traffic"*, rated Critical in `business-analysis.md` §11) has not ruled on that. Choosing it would
pre-empt an unanswered question about the group's data.

**A `/metrics` endpoint with nothing scraping it.** Rejected because it does not deliver the one Success
row that needs this stack. A p95 over 20 recorded runs requires something storing samples over time;
without it, the only instrumented metric in the whole table becomes a manual exercise.

## Consequences

- Every module's observability rows name metrics under `prope_<module>_<name>_<unit>` and are checked
  against the cardinality rule above at each per-module pass, rather than discovered when Prometheus
  exhausts memory.
- Log retention is bounded and small by design. An incident investigated more than a few days later is
  reconstructed from `history_event` and `call_record`, which is where the durable answers live anyway —
  and which is a statement about Prope's design rather than a limitation of this choice.
- Two services, roughly 550 MB, and no data leaves the VM.
- The gateway p95 histogram is the artefact that would justify a future language deviation under
  ADR-0026 and the process split under A-130. It exists from the first deployment, so both triggers are
  measurements rather than arguments.

# Coverage — Phase 3: Durability, idempotency, and no-read-path

> **The deterministic `api-coverage.cjs` detector is not available in this environment.** The GSD
> toolchain is not installed (ORCHESTRATION §0) — there is no `bin/lib/*.cjs`, so no detector was run
> and **no detector verdict is reproduced or invented**. Everything below is an **agent enumeration**,
> reached by reading the phase's CONTEXT, RESEARCH and PATTERNS artifacts, the lock file and the
> installed wheels. Phase 2's COVERAGE.md recorded `{"detected": false, "signals": []}` from the real
> binary and then recorded a matrix anyway, on the ground that a broker is a real external service
> with a real capability surface. The same posture is taken here for the same reason.

---

## Part 1 — Plan / requirement / success-criterion mapping

**Every requirement id this phase owns appears in exactly one plan's `requirements:` field, and every
ROADMAP success criterion is owned by exactly one plan.**

| Plan | Wave | `requirements:` | ROADMAP SC owned | Subject |
|---|---|---|---|---|
| `03-01` | 1 | `CL-01` | **SC1** | The direct-write fallback, the byte cap, the shutdown drain, the eighteen metrics defined at import |
| `03-02` | 2 | `CL-02` | **SC2** | The idempotent upsert and the aggregate derived from the returned set |
| `03-03` | 2 | `CL-07` | **SC3** | `ceiling_check_total{result}` on all three branches; CR-01's bound |
| `03-04` | 3 | *(none — see below)* | — | `/metrics`, the depth gauges, `oldest_body_age_seconds`, the alert rules |
| `03-05` | 4 | `CL-10` | **SC4** | The three-layer no-read-path sweep and the fourth reader |
| `03-06` | 4 | `CL-12` | **SC5** | The enqueue budget, measured |

**`03-04` carries no requirement id, and that is a fact about `REQUIREMENTS.md` rather than about the
work.** The phase's ROADMAP Spec line names `observability_requirements.metrics` (all seventeen) and
`alerts` (all six) explicitly, and `security_requirements` T-005's mitigation names
`prope_call_ledger_dlq_depth` and its alert — but none of the project's 89 requirements is written
against observability, so there is no id to claim. It is recorded here so a verifier reads
`requirements: []` as deliberate rather than as an omission.

### Wave disjointness

Two plans in the same wave must have **provably disjoint** `files_modified`. They do:

| Wave | Plans | Disjointness |
|---|---|---|
| 1 | `03-01` alone | — |
| 2 | `03-02`, `03-03` | `03-02`: `writer.py`, `domain.py`, `drain.py`, `test_write_path.py`, `test_drain_failure_classification.py`, `test_redelivery_leaves_the_total_unmoved.py`, `test_no_sql_interpolation.py`. `03-03`: `seams.py`, `schemas.py`, `observability.py`, `test_ceiling_refuses_evals_only.py`, `test_management_routes.py`, `test_retention_days_bound.py`. **No overlap.** |
| 3 | `03-04` alone | Touches `app.py` (which `03-01` owned in wave 1), `test_route_table.py` (same), and `pyproject.toml` (which `03-06` touches in wave 4). All three collisions are **cross-wave and therefore serialised**, not parallel. `uv.lock` was added to `03-04`'s `files_modified` at the critique pass — Task 4 runs `uv sync` and an acceptance criterion asserts the lock moved in the same commit, so it was a file touched by an action and absent from the frontmatter. No other plan touches it. |
| 4 | `03-05`, `03-06` | `03-05`: `tests/security/*`, `OQ-025.md`. `03-06`: `tests/load/*`, `pyproject.toml`, `Makefile`. **No overlap.** |

### `D-NN` and `OQ-NNN` allocation actually consumed

- **Decisions: `D-26` … `D-45`**, all twenty, exactly the range `03-CONTEXT.md` allocated. **The plans
  allocate no new decision numbers.** The CONTEXT Discretion items are resolved *inside* the plans in
  Phase 2's posture — the resolution is written at the code and recorded in the plan — rather than
  promoted to new `D-NN` ids. **Phase 4 starts at `D-46`.**

  | Decision | Landing plan |
  |---|---|
  | D-26, D-27, D-28, D-29, D-31, D-32, D-41 | `03-01` |
  | D-30, D-33, D-34, D-35, D-36 | `03-02` |
  | D-37 | `03-03` |
  | D-38 | `03-05` |
  | D-39, D-42, D-43, D-44 | `03-04` |
  | **D-40** *(split, by subject)* | `03-01` defines all eighteen metrics at import; `03-02` adds the `missing_version_id_total` refusal and the `unpriced` / `unknown` increments; `03-03` ships `ceiling_check_total{result}` and retires `ceiling_failed_open_total` |
  | **D-45** *(split, by part)* | `03-01` owns part 3 (the broker-outage provocations); `03-06` owns parts 1 and 2 (the proxy and the marked run) |

- **Open questions: `OQ-022` … `OQ-026`**, all five, exactly the range allocated. All five are raised,
  as `03-CONTEXT.md` requires.

  | Id | Raised by | Blocks |
  |---|---|---|
  | `OQ-022` | `03-01` | `call-ledger.lock.yml` `observability_requirements.metrics` — four clauses; **plus a fifth against `failure_modes` row 2 and `alerts` `LedgerPublishFailing`**, added at the critique pass, because `publish_failed_total` cannot rise in the outage its detection narrative is written about |
  | `OQ-023` | `03-04` | `call-ledger.lock.yml` `observability_requirements.metrics` — `unpriced_total`'s per-workspace labels on an unauthenticated route |
  | `OQ-024` | `03-01` | `call-ledger.lock.yml` `test_plan.chaos` and `test_plan.unit` |
  | `OQ-025` | `03-01` (clause 1), **appended by `03-05`** (clause 2) | `call-ledger.lock.yml` `security_requirements` T-005 / A-149, and ADR-0037 |
  | `OQ-026` | `03-04` | ADR-0028 / D-17 against `observability_requirements` and `alerts`; **plus a second clause against `apis.exposes`**, added at the critique pass — `/metrics` is the eighth served path and the `exposes` line `interfaces.md:1236-1239` says step 6 owed was never added |

  A **sixth** conflict was found during research (`prope_report`'s `SELECT` on `ledger.call_body`) and
  has **no allocated id**. It is filed as `OQ-025`'s second clause rather than as `OQ-027`, because
  both clauses are the same question — *a stored body rests somewhere no assertion in this repository
  reaches* — and because **OQ-027 may belong to the phase being planned in parallel**. No id outside
  the allocated range is claimed.

---

## Part 2 — External surface enumeration

This phase integrates **one genuinely new external surface** and **extends one already enumerated**.
`INTEGRATE` is the default; every `OPT-OUT` carries a written reason.

### 2a. Prometheus — the exposition format and the alerting-rules format (NEW)

**Why a matrix rather than a no-integration declaration.** ADR-0030 puts Prometheus and Grafana in the
stack, and this phase ships the first surface anything outside the process can read: an HTTP
exposition endpoint and a rules file in Prometheus's own schema. Neither is a library call — both are
**contracts with a service the deployment stack will eventually run** — and "we integrated whatever
the first metric needed" is exactly the hole this matrix exists to close.

**Surface enumerated:** the capability set reachable through `prometheus-client==0.26.0` plus the
Prometheus alerting-rules file format.

| capability | decision | reason |
|---|---|---|
| `Counter` | INTEGRATE | |
| `Gauge` (`.set()`) | INTEGRATE | first use in this project — `queue_depth`, `dlq_depth`, `oldest_body_age_seconds` |
| `Histogram` with explicit `buckets=` | INTEGRATE | first use; the defaults cannot measure either of this phase's latency claims |
| Closed, source-fixed label sets on every metric | INTEGRATE | ADR-0030's cardinality rule, enforced by the existing `REGISTRY.collect()` walk |
| `generate_latest(REGISTRY)` over the default process registry | INTEGRATE | |
| `CONTENT_TYPE_PLAIN_0_0_4` as the declared media type | INTEGRATE | `generate_latest` emits the 0.0.4 format; `CONTENT_TYPE_LATEST` declares 1.0.0 in 0.26.0 |
| HTTP exposition on a path the route table can see | INTEGRATE | a plain `APIRoute` on `app` |
| Alerting-rules file (`groups` / `rules` / `alert` / `expr` / `for` / `labels` / `annotations`) | INTEGRATE | as a repository artifact with a test, not as a running service |
| `make_asgi_app()` / `app.mount("/metrics", ...)` | **OPT-OUT** | a `Mount` carries no `dependant`, so `assembled_routes()` skips it and it appears in neither the route-table assertion nor the OpenAPI schema — a served path every assertion in the repository is blind to, which is the shape AC-10 exists to refuse. It also serves `/metrics/` with a 307 in front of `/metrics` |
| `choose_encoder` / `Accept`-header content negotiation | **OPT-OUT** | negotiation is a feature nothing in this deployment asks for; one scraper, one format. The constant is one line and is what the library itself defaults to |
| OpenMetrics exposition (`generate_latest` + `CONTENT_TYPE_OPENMETRICS`) | **OPT-OUT** | exemplars and native histograms are the features it buys, and this phase has no tracing to attach exemplars to (distributed tracing is a recorded rejection under A-012) |
| `multiprocess` mode over a shared `PROMETHEUS_MULTIPROC_DIR` | **OPT-OUT** | genuinely viable and named as the strongest rejected answer in `OQ-026`: one image, one host, one compose file. It needs a writable volume shared between two containers and degrades gauges to a chosen reduction mode, and it is a **deployment-stack change in a stack that owns no milestone** (PITFALLS §4) |
| `push_to_gateway` / Pushgateway | **OPT-OUT** | the standard answer for a producer with no scrape surface, and ADR-0033 fixes the runtime at **seven services**. Recorded in `OQ-026` |
| `start_http_server()` on `worker` | **OPT-OUT** | D-17 — *"`worker` consumes and never serves HTTP"* — is **derived from ADR-0028**, not chosen, so it is not this phase's to reverse. It would also add the surface T-02-15 registers and would redden `test_worker_imports_no_web_framework`, whose forbidden import set already includes `http` and `socket` |
| A custom `CollectorRegistry` per module | **OPT-OUT** | one process, one registry; a second registry is a second thing `generate_latest` must be told about, and the existing cardinality walk is written over the default one |
| `Summary` with quantiles | **OPT-OUT** | client-side quantiles cannot be aggregated across instances and cannot be re-quantised; `Histogram` with argued edges is what both of this phase's targets need |
| `Info` / `Enum` metric types | **OPT-OUT** | nothing here reports a build version or a state machine; the lock file declares none |
| `@Histogram.time()` / `@Counter.count_exceptions()` decorators | **OPT-OUT** | the timed span is chosen precisely (the whole of `enqueue()` and nothing else) and a decorator would tie it to a function boundary that may move |
| `platform_collector` / `process_collector` / `gc_collector` (the default collectors) | INTEGRATE (by default, unmodified) | they arrive with the default registry, they are what a scrape of a Python process is expected to carry, and removing them would be a decision nobody asked for |
| Prometheus **recording** rules | **OPT-OUT** | the six declared alerts are all expressible directly; a recording rule would put a second definition of a threshold in a file nothing evaluates |
| Alertmanager routing / inhibition / silences | **OPT-OUT** | the rules file declares `severity` and stops there. Routing is a deployment concern and the deployment stack owns no milestone |
| `promtool check rules` in CI | **OPT-OUT** | it is the only thing that would prove the file is a *valid* rules file, and the binary is not obtainable in this environment. The boundary is stated at the test: it proves well-formed YAML and real metric names, and nothing more |
| Grafana dashboards / provisioning | **OPT-OUT** | ADR-0030's one dashboard is a deployment artifact; PITFALLS §4 gives it no owning milestone |

### 2b. AMQP / RabbitMQ 4.x — delta against Phase 2's matrix

Phase 2 enumerated this surface in full. Only the rows that **change** are restated; every other row
stands as recorded.

| capability | Phase 2 | Phase 3 | reason |
|---|---|---|---|
| `queue.declare` with `passive=True` (`declaration_result.message_count`) | not enumerated | **INTEGRATE** | D-42's depth gauges. A passive declare checks existence and reports counts **without comparing arguments**, so it can never answer `406 PRECONDITION_FAILED` against D-23's one-way arguments — which is why it, and not a full redeclare, is the read |
| Management HTTP API `GET /api/queues/...` for depth | INTEGRATE (test only) | **OPT-OUT for production** | `_helpers.py`'s own comment: *"the management API's statistics refresh on an interval and a test that read depth from it would be racing a scheduler."* The same is true of a gauge. It stays in use for the declared-argument read-back test |
| `AbstractIncomingMessage.redelivered` | asserted in one test | **INTEGRATE** | D-35's `redelivered_total`, the broker's own view of what it re-sent |
| `x-max-length-bytes` on the work queue | not declared | **OPT-OUT, and raised** | It was never declared and cannot be added now without D-23's delete-and-redeclare in every environment that has run. The producer-side cap (`MAX_BODY_BYTES`) bounds one message and does not bound the queue; the residue is `OQ-025`'s first clause |
| A second broker queue, or broker-based cache invalidation | OPT-OUT | **OPT-OUT (unchanged)** | Proposed twice, rejected twice on merit. Nothing here declares a third queue |

### 2c. PostgreSQL 17 — delta

Not a new integration; the database has been integrated since Phase 1. Two capability rows change and
are recorded because both are first uses.

| capability | decision | reason |
|---|---|---|
| `INSERT … ON CONFLICT (col) DO NOTHING … RETURNING` | INTEGRATE | D-33. *"Only rows that were successfully inserted or updated will be returned"* is the whole mechanism CL-02 rests on |
| SQLAlchemy `insertmanyvalues` batching of the above | INTEGRATE | on by default for asyncpg (`insertmanyvalues_page_size=1000`), so a 500-record window is one round trip rather than 500 |
| `sort_by_parameter_order=True` on the returning clause | **OPT-OUT** | it makes `call_id` a client-side sentinel and raises `InvalidRequestError` the first time `ON CONFLICT` skips a row — which is CL-02's own scenario. The returned ids are used as a **set**, so no ordering is needed |
| `INSERT … ON CONFLICT DO UPDATE` | **OPT-OUT** | re-prices an existing record against ADR-0019, and PostgreSQL requires `UPDATE` privilege, which `prope_app` deliberately does not hold on `ledger.call_body` |
| `MERGE` (PostgreSQL 15+) | **OPT-OUT** | no `RETURNING` on the rows it affected in PG 17, which is the one thing this phase needs; and it is a second statement shape for a job `ON CONFLICT` already does |
| Advisory locks to serialise the drain | **OPT-OUT** | exactly one consumer is a Phase 2 correctness property already asserted against the broker's own view; a lock would be a second mechanism for one guarantee |
| A `SECURITY DEFINER` function to enumerate workspaces for the age gauge | **OPT-OUT** | exactly four are sanctioned and a test asserts the set is those four. The correct answer is the enumerator parameter Phase 7 fills |
| `REVOKE SELECT ON ledger.call_body FROM prope_report` | **OPT-OUT, and raised** | Plan 03-05's adopted-UNCONFIRMED decision. The grant is left, the exposure is asserted by a named test, and the question is `OQ-025`'s second clause |

### 2d. Nothing else external is integrated, and here is the list of what was checked

Stated rather than padded. This phase adds **no new runtime dependency of any kind** — every library
it needs is already pinned and already installed — and the only `pyproject.toml` dependency change is
`pyyaml==6.0.3` moved from a transitive extra of `uvicorn[standard]` into an explicit dev-group pin,
so that a test about alert rules does not break on an unrelated web-server upgrade. No HTTP client, no
scheduler, no benchmark plugin, no YAML alternative, no tracing library, and no second broker client
is added. `promtool`, a running Prometheus and a running Grafana are all **unavailable and out of
scope**, and each is recorded above as a boundary rather than as a gap.

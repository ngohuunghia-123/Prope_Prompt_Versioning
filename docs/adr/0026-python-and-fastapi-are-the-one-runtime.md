# ADR-0026 — Python 3.13 and FastAPI are the one runtime for all eight modules

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user (confirmed the inherited runtime), agent (version, LangGraph removal)
**Module**: global — cited as `Inherited` by every module's Language and Web-framework rows
**Related**: A-012, A-031, A-114, A-127, ADR-0022, ADR-0033, OQ-005, OQ-012

## Context

`00_context.md#constraints` records the stack as inherited rather than chosen:

> "Stack: Python, FastAPI, LangGraph, PostgreSQL, Next.js, Docker | language_preference |
> `BRIEF.md` header; existing repo (`src/`, `requirements.txt`, `Dockerfile`) | **Non-negotiable: no**
> | Inherited from the hackathon template; confirm or replace in step 4"

Inspecting the repository showed the row overstates what exists. `fastapi>=0.115`, `uvicorn[standard]`,
`pydantic>=2.10` and a working `src/main.py` are real; the Dockerfile pins **3.11**. `sqlalchemy`,
`alembic` and `psycopg2` are **commented out** in `requirements.txt` and `docker-compose.yml` declares
no database service at all. There is no `package.json` anywhere. `langchain` and `langgraph` are
installed and used only by a boilerplate `src/agents/graph.py` with one example node and one example
tool.

So the decision is narrower than "confirm or replace the stack": Python and FastAPI are genuinely
inherited and running; everything else in that row is an intention.

The case against Python is one number, and it belongs to one module. `00_context.md#success` requires:

> "Latency the gateway adds on top of the upstream call | p95 < 50 ms | Instrumented span from request
> arrival to upstream dispatch, plus upstream completion to response flush; logging excluded by
> construction"

tightened by the `gateway → access-control` seam to *"a stated budget of p95 < 5 ms inside the gateway's
50 ms"* on a check that ADR-0022 forbids caching.

Examined honestly, that budget is not spent by the language. The uncached permission check is a
PostgreSQL round trip and costs the same in any runtime. The genuinely Python-shaped risks are three,
and all three are addressable inside Python: per-chunk JSON serialisation in the SSE relay loop, a
streaming path that silently buffers, and A-087's post-flush enqueue not actually running post-flush.
Further, the 50 ms figure is itself agent-decided — the constraints table says so in its own Notes
column (*"The strategy is yours; the number is mine until you replace it"*, A-031) — and OQ-012, which
would supply a real one, is still open.

## Decision

**Python 3.13, pinned to a patch release, with FastAPI, is the single runtime for all eight modules.
One image, one dependency set, one CI lane.**

- The version moves **3.11 → 3.13**. This is free today because no code beyond boilerplate survives the
  build, and 3.11 approaches end of security support inside the pilot's expected life.
- **FastAPI is inseparable from this choice** and is recorded here rather than in a per-module row.
  Every module with an HTTP surface cites this ADR as `Inherited`; a module with no HTTP surface
  records `n/a` with its reason — property-history being the case that already exists (A-123).
- **`langchain` and `langgraph` are removed** (A-127). Nothing in `00_context.md#scope` is a graph:
  the gateway resolves a model name to a revision and forwards one HTTP call, and evaluation runs N
  cases against deterministic assertions. A-011 fixes a prompt body at *"one plain-text system message
  with optional `{{variable}}` placeholders"* — there is no branching agent, no tool loop, and no state
  machine over model turns.
- Three hot-path rules are stated here because they are the whole of the Python-specific risk:
  `orjson` and never the stdlib `json` in the SSE relay loop; the response body is streamed and never
  `aread()` into memory; the enqueue in A-087 happens after the response is flushed and is asserted by
  a test rather than assumed.
- **The named revisit condition is a gateway-only deviation**, and it is triggered by measurement, not
  by opinion: OQ-012 supplying a real RPS and latency figure, followed by a load test that misses it.
  The instrumented span exists from day one either way, so that test replaces a placeholder rather than
  starting an argument about how to measure.

## Alternatives rejected

**Go 1.2x as the baseline for all eight modules.** Rejected on cost against a number nobody has
validated. It buys real p95 headroom, but the p95 in question is an agent-decided placeholder against
an unknown RPS, and paying for it means discarding a working FastAPI skeleton and rewriting eight
modules whose specifications were written this week. The gateway's actual latency floor is a database
round trip that Go does not make faster.

**A split runtime: Go (or Rust) for the gateway, Python for everything else.** Rejected as the most
expensive possible answer to `00_context.md#constraints`: *"The whole system must run for one small
team with no dedicated ops."* Two toolchains, two images, two dependency-vulnerability surfaces, and
two CI lanes, permanently, to protect one module's placeholder budget. It stays available as a
superseding ADR under the measured trigger above — the point of naming the trigger is that this
becomes a decision with evidence rather than a rewrite under pressure.

**Node/TypeScript for the whole system, unifying with the frontend.** Rejected because it discards the
only part of the inherited stack that actually exists and works, ~~in exchange for a unification that
ADR-0034 makes unnecessary — the UI is server-rendered from the same Python process and there is no
second language to unify with.~~

> *Amended 2026-08-09.* **The second half of that sentence is withdrawn.** ADR-0052 superseded ADR-0034:
> the UI is a React + TypeScript SPA, so there **is** now a second language, and the unification argument
> this rejection dismissed as unnecessary is live again. **The rejection stands unchanged on its first
> half**, which was always the load-bearing one — Python and FastAPI are *"the only genuinely inherited,
> working part of the stack"*, and a JavaScript build lane in CI is not a reason to rewrite eight Python
> modules, a PostgreSQL data layer built on `SECURITY DEFINER` functions and RLS policies, and every ADR
> from 0027 to 0051. The honest position after ADR-0052 is that Prope is a two-language system by
> deliberate choice, with the boundary at the HTTP seam and nothing crossing it but JSON.

**Staying on Python 3.11 (the Dockerfile's current pin).** Rejected because it is a free bump today
and a chore later: no code beyond boilerplate survives, and 3.11 reaches end of security support inside
the pilot's expected life. Deferring costs strictly more than doing it now.

**Python 3.14.** Rejected as unnecessary risk. Its headline feature is free-threading, which buys
nothing for an IO-bound workload waiting on upstream model calls, while wheel availability for the
less-common dependencies is still thinner than on 3.13.

## Consequences

- One image serves `app` and `worker` (ADR-0028) — different commands, identical build. That keeps the
  build matrix at one entry despite two running services.
- The `libraries_frameworks` field in all eight lock files can be filled from this ADR plus A-128's
  data-access baseline, rather than negotiated per module.
- Dropping `langchain` and `langgraph` removes a large transitive dependency tree, which shortens both
  the image build and the surface a dependency audit has to cover.
- The gateway's p95 becomes a **load-test result** rather than a design assumption, and the load test
  is now the artefact that would justify a future split. `module_map.md`'s `gateway — Estimable: no`
  score is unchanged by this ADR: it was never the language that made the module hard to estimate.
- CPU-bound work now shares a process with the gateway. That is accepted for the pilot and bounded by
  A-130, which names the split trigger and the histogram that fires it.

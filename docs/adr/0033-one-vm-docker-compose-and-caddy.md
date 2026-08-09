# ADR-0033 — One group-controlled VM, docker-compose, and Caddy as the single ingress

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global
**Related**: A-012, A-019, A-020, A-113, A-129, A-130, ADR-0026, ADR-0028, ADR-0030, ADR-0031,
ADR-0032, ADR-0034, OQ-011, OQ-012, OQ-013

## Context

OQ-011 was open: *"Where does the demo run: a laptop, or something hosted?"* A-019 proposed local
docker-compose as the working default. Two constraint rows pull against each other:

> "The whole system must run for one small team with no dedicated ops | ops_capacity | A-012 | no |
> One `docker-compose up`; no broker, no separate worker fleet"

> "Prope is an accepted hard dependency of consuming products' request paths | deploy_target | user —
> 2026-08-08 (OQ-012) | **yes** | No consumer-side fallback is assumed; a Prope outage is a full outage"

A laptop cannot be a hard dependency of anything. But the second row already accepts the availability
consequence explicitly — `00_context.md#scope` records it as *"an accepted risk, not a mitigated one"* —
and a single VM has the same single-failure-domain shape as a laptop without the lid. So single-VM is
consistent with what step 1 signed off rather than a quiet downgrade of it.

The host is a policy question rather than an architecture preference, because two non-negotiable rows
put other people's secrets and other people's request bodies on whatever box is chosen: the credential
row quoted in ADR-0032, and *"Request and response bodies are stored; retention, read access, and PII
handling must be settled before any real traffic"* — with OQ-013 unresolved and rated Critical in
`business-analysis.md` §11.

## Decision

**One Linux VM the group controls, running docker-compose. Caddy is the single ingress and terminates
TLS. A laptop is the development and demo target only.**

Seven services:

| Service | Role |
|---|---|
| `caddy` | TLS termination, single ingress, **and the SPA's static assets baked into the image** (ADR-0052) |
| `app` | FastAPI — management API and gateway (ADR-0050). **No longer renders the UI** (ADR-0052 supersedes ADR-0034) |
| `worker` | Same image as `app`, different command — RabbitMQ consumer (ADR-0028) |
| `postgres` | PostgreSQL 17, all eight schemas (ADR-0027) |
| `rabbitmq` | RabbitMQ 4 (ADR-0028) |
| `prometheus` | Metrics (ADR-0030) |
| `grafana` | Dashboards (ADR-0030) |

- **Caddy is not optional and is not a consequence of the frontend choice.** Consumer API keys travel in
  `Authorization` headers (A-113), so TLS termination was required regardless of how the UI is rendered.
  A-129 records it as the single ingress. *Amended 2026-08-09* — that independence is what made ADR-0052
  cheap: Caddy was already there, already the one origin, and already routing, so hosting a React SPA cost
  it a `root`/`file_server` block rather than a new component. **`caddy` is now a built image rather than
  a stock one** (`FROM caddy:2` + the Vite output), so the deploy pulls **two tags**, `prope-app` and
  `prope-web`. ADR-0031's *"host pulls, never builds"* is preserved; the count stays at seven services.
- **Sizing**: 4 vCPU, 8 GB RAM, 80 GB SSD, plus 2 GB swap. Steady-state memory is roughly 2.7–3.1 GB;
  4 GB runs but leaves about 1 GB of page cache for PostgreSQL, which is where the difference is
  actually felt. PostgreSQL is tuned off its 128 MB default — `shared_buffers=1GB`,
  `effective_cache_size=4GB`. Every service carries a `mem_limit` so one runaway container cannot
  OOM the host, `prometheus` and `postgres` most of all.
- **Disk growth has exactly one unbounded term: `call_body`.** At roughly 10 KB per call and 10k calls a
  day, that is about 3 GB per month at A-040's placeholder 30-day retention. A disk-usage alert sits
  beside A-106's oldest-body gauge, because that pairing is what turns an unanswered policy question
  into a full disk rather than an alert.
- **No HA, deliberately.** A restart is downtime. That is the shape `00_context.md#scope` already
  accepted, and pretending otherwise would require a second host, a load balancer, and a PostgreSQL
  replication story that A-012 has no budget for.

## Alternatives rejected

**A laptop, per A-019's literal proposal.** Rejected as insufficient for anything past the demo. It is
adequate for the timed usability script and the observed demo run, and it cannot host a pilot that other
people depend on. Kept as the development target, which is what the existing `docker-compose.yml`
already serves.

**Managed PaaS — Render, Railway, or Fly.io.** Rejected on data rather than capability, and it is the
option with the strongest practical case: near-zero operational burden and the fastest path to a URL.
Choosing it would place workspace provider credentials and stored request and response bodies in a
vendor's data plane in a region nobody has named, which re-opens the residency half of OQ-013 that
`module_map.md` had just parked as *"a deployment question step 4 owns."* Deciding it here would be
answering a question about the group's data on the group's behalf.

**A cloud VM on a personal or team account.** Rejected as the same architecture with a worse ownership
story. It is technically identical to the decision, and it makes "who owns the account holding a
subsidiary's API keys" a question that surfaces at the least convenient time.

**Kubernetes.** Rejected against A-012 without qualification. That constraint row exists to stop exactly
this: a cluster is a component that requires its own runbook, and the stack already carries a broker it
did not originally have.

## Consequences

- **A-012 and the `ops_capacity` constraint row are amended.** The real figure is seven services, not
  one `docker-compose up` with no broker and no worker. The row is corrected rather than left
  contradicting the stack, because a constraint the build disagrees with is worse than a constraint that
  admits what changed.
- **OQ-011 is resolved.** Its residency sub-question is answered by consequence: nothing leaves the
  host, which is also why ADR-0030 refused a hosted telemetry backend.
- The revisit condition is a person, not a metric: **the first consuming product that treats Prope as a
  hard dependency in production.** That is when "accepted risk" starts meaning somebody else's outage,
  and when HA stops being unaffordable and starts being owed.
- ADR-0031's deploy account, ADR-0032's `.env`, and the PostgreSQL and Prometheus tuning above are the
  host's entire hand-managed state. Everything else is a pulled image.
- Backup is not settled here. It is per-module tier and belongs with each module's datastore row — but
  the host-level fact is recorded now: `.env` must be backed up **separately from and never alongside** a
  `pg_dump`, or the backup contains both the ciphertext and its key.
  **Settled 2026-08-09 by ADR-0036**, during property-history's step-4 pass: nightly `pg_dump -Fc`
  copied to a second group-controlled machine, 30-day retention, RPO 24 h / RTO ~10 min. The `.env` rule
  above is carried into it verbatim. One consequence lands back here — **object storage is rejected as
  the destination because it contradicts this ADR's own residency answer** (*"nothing leaves the
  host"*), and A-131 records that the second machine may not exist yet.

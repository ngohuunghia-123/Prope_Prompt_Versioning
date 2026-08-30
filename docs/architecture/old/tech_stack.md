# Technology Stack

> **Status**: locked
> **Last updated**: 2026-08-09
> **Progress**: 8/8 modules — step 4 complete

Written by `bsp-4-tech-stack`. The **authoritative** record of what is complete is which module
subsections exist under `## Per-Module Stack`; the `Progress:` line is a convenience.

Module order (dependency-first, confirmed by the user 2026-08-09): `property-history` → `call-ledger` →
`access-control` → `provider-access` → `prompt-registry` → `evaluation` → `gateway` → `release-control`.

### Lock check, 2026-08-09

Every criterion verified rather than asserted:

- Global Baseline covers all eleven global-tier concerns — **zero TBDs in this file**.
- Eight per-module subsections, one per module in `module_map.md`, each with a row for every per-module
  concern. **No blank cells**; `n/a` always carries a reason.
- Every global baseline choice has an ADR (ADR-0026 … ADR-0035, plus ADR-0036/0037 established during
  property-history's pass). The one global row without one is **ML stack**, which is `n/a` — there is no
  decision to record.
- Every `Deviated` row cites an ADR written in the same pass; every `Inherited` row cites the baseline
  ADR. **Fourteen ADRs across the eight module passes** — ADR-0038 … ADR-0051 — which is genuine
  divergence rather than one per module: call-ledger and access-control account for three each, while
  **release-control deviates on one row and inherits every other**. Three of the fourteen are global in
  scope despite being found in a module pass (ADR-0036, ADR-0037, ADR-0045).
- Every ADR quotes at least one line from `00_context.md#constraints` or cites an `A-NNN`; every rejected
  alternative names a specific reason it lost.
- All eight lock files carry `language_runtime`, `deployment_target` and `libraries_frameworks` with ADR
  citations. **Zero `#TBD-step-4` markers remain in `docs/modules/`.**
- **51 ADR files, 51 index rows. 140 assumption files, 140 index rows.**
- Each of the nine blocks — one baseline, eight modules — was approved by the user before anything was
  written.

**What step 4 changed that step 3 did not expect.** Twenty-six ADRs were written here (ADR-0026 …
ADR-0051), and the recurring find was not a technology choice but a **claim resting on a premise a later
decision had removed** — one in each of the last four passes: prompt-registry's model-catalogue cache,
A-063's dispatch clause, the gateway's stale-if-error, and ADR-0012's pub/sub rejection. The first three
were adopted mechanisms; the fourth was a *rejected alternative*, which is the harder shape to catch.
**Eight tables gained a `workspace_id` column across six passes**, three of them found by hand before
ADR-0045 inverted the rule and made the rest a CI failure; the sanctioned
`SECURITY DEFINER` set grew from two to four; and two mechanisms (the spill file, stale-if-error) were
deleted rather than built. Step 6's sweep inherits a list of owed acceptance criteria, recorded in each
lock as it was found.

## Global Baseline

| Concern | Choice | Version / Range | Rationale | ADR | Alternatives rejected |
|---------|--------|-----------------|-----------|-----|----------------------|
| **Language (baseline)** | Python | pinned 3.13.x | The only genuinely inherited, working part of the stack. The gateway p95 is a load-test question, not a language one — the number itself is an agent-decided placeholder (A-031) against an RPS OQ-012 has not supplied | ADR-0026 | Go baseline (cost against an unvalidated number); split Go gateway + Python (two toolchains against *"one small team with no dedicated ops"*); Node/TypeScript everywhere (discards the working part, and ADR-0034 removes the unification argument); Python 3.11 (free bump now, chore later); Python 3.14 (free-threading buys nothing IO-bound) |
| **Web framework (baseline)** | FastAPI + uvicorn + pydantic v2 | fastapi ≥0.115, pydantic ≥2.10 | Inseparable from the language choice and already running. Per-module rows cite this ADR as `Inherited`; a module with no HTTP surface records `n/a` | ADR-0026 | — (folded into the language decision) |
| **Database engine (baseline)** | PostgreSQL — one instance, one database, **schema per module**, roles `prope_app` + `prope_migrate` | 17.x | ADR-0025 needs role privileges; ADR-0023 forbids database-per-module because an append runs in the caller's transaction; BR-03 needs a database constraint; A-118/A-119/A-124/A-125 need `jsonb`, partial indexes, `bigserial` and a SQL set filter | ADR-0027 | SQLite (no roles, single-writer, weak JSON — three independent fatals); database per module (breaks ADR-0023); one shared `public` schema (keeps the defect, and expensive to retrofit); role per module (right idea, 8 pools, adoptable later without moving data); MySQL/MariaDB (no RLS, so ADR-0035 has no mechanism) |
| **Tenant isolation** | PostgreSQL row-level security — `workspace_id = current_setting('app.workspace_id')`; `prope_migrate` owns and bypasses, `prope_app` is subject | — | A missing filter returns **zero rows** instead of another tenant's data. Same enforcement move as BR-03, ADR-0025 and ADR-0027; the only one still resting on convention | ADR-0035 | App-level filtering only (silent, unbounded failure; breaks BR-01 quietly); database or schema per workspace (breaks ADR-0023, fans out migrations); deferring until OQ-007 answers (asymmetric — one line per table now, a migration per table plus a re-audit later) |
| **Message broker** | RabbitMQ | 4.x | User decision, 2026-08-09. Three genuinely asynchronous workloads; purpose-built retry, acknowledgement and dead-lettering rather than reimplemented over a table. **Supersedes the "no broker" clause of A-012 and A-037** | ADR-0028 | No broker / PostgreSQL as queue (recommended, lost to the user's decision — recorded with its full case); Kafka (1–2 GB and the fiddliest config, for replay serving an out-of-scope feature); NATS JetStream (lightest, thinnest Python client and literature — and A-012's real currency is 3am debuggability); Redis (its other two jobs are already forbidden by A-080 and A-114) |
| **Identity provider** | Local — Prope `user` table, argon2id, **server-side session rows**, HttpOnly same-origin cookie | — | A-108 confirmed by the user, `agent` → `human`. A-020 bars real corporate prompts from the pilot, so there is no corporate identity to federate; A-110's no-invitation flow is only coherent without an IdP | ADR-0029 | OIDC against the group IdP (unscoped: discovery, callback, JIT provisioning, app-registration ownership — supersedes rather than amends if policy requires it); self-hosted Keycloak (pays both costs, adds a service, protects no better against host compromise); self-contained JWTs (contradicts ADR-0022 — revocation would wait for expiry); magic links (ruled out by A-071, no email) |
| **Observability** | Prometheus + Grafana; `prometheus-client`, `structlog` JSON to stdout; `json-file` capped at `50m × 5` | — | A-046 already pinned Prometheus-shaped metric names. Exactly one Success row needs a histogram; most are SQL over PostgreSQL, and `history_event` is already a structured, indexed, never-deleted event store (A-121) | ADR-0030 | Loki (chosen then dropped — one host, and adding it later costs ~30 min and forfeits nothing; the 1-container variant kills `docker compose logs`); distributed tracing (one process — a trace with no distribution is a log line with a duration); hosted OTel free tier (sends model names and workspace IDs off-box; OQ-013 has not ruled on that); `/metrics` with no scraper (no sample history, so the one instrumented Success row becomes manual) |
| **CI/CD** | GitHub Actions → GHCR → CD over SSH to a forced-command deploy account; host pulls, never builds | — | User decision, 2026-08-09. Four step-3 promises become build failures: ADR-0025's privilege, A-123's empty route table, BR-03's constraint, A-124's allow-list | ADR-0031 | Test + publish with manual `make deploy` (recommended, lost to the user's decision; retained as the fallback if inbound SSH is refused); self-hosted runner on the VM (puts a toolchain and a GitHub-triggered execution surface beside the credentials); build on host (non-reproducible; the tested artefact is not the deployed one); defer deployment (the first deploy is then improvised under pressure) |
| **Secrets manager** | One `.env` on the VM, `0600`, git-ignored, `env_file:`. Holds the **KEK**, Postgres password, RabbitMQ credentials, session key. Never enters CI | — | Settles ADR-0014's deferred KEK store. Defeats the dominant threat (dump / backup leak) identically to any alternative, because the key is outside the database either way | ADR-0032 | compose `secrets:` file mounts (recommended, lost to the user's decision; residual gap closed by the `SecretStr` and no-`os.environ`-logging rules); cloud KMS (the only option surviving a stolen disk image — named as the upgrade path, triggered by A-020's sign-off); self-hosted Vault (worst ratio: a service with an unseal procedure that protects no better against host compromise); KEK in the database (makes envelope encryption decorative) |
| **Container / orchestration** | Docker + docker-compose on **one group-controlled Linux VM**; **Caddy** single ingress + automatic TLS. 7 services | Ubuntu 24.04 LTS | Resolves OQ-011. Matches A-012 and A-019; single-failure-domain shape is what `00_context.md#scope` already accepted (*"an accepted risk, not a mitigated one"*). Nothing leaves the host, which also keeps OQ-013's residency half closed | ADR-0033, A-129 | Laptop only (cannot host a pilot others depend on); managed PaaS (credentials and stored bodies in a vendor data plane in an unnamed region — re-opens OQ-013); personal cloud account (same architecture, worse ownership story); Kubernetes (A-012 exists to stop this) |
| **Frontend** | **React 19 + TypeScript SPA, built with Vite. Tailwind 4 via `@tailwindcss/vite`.** Node in **CI only** — the build is baked into a second image, `FROM caddy:2`, and Caddy serves `/` from `/srv` while proxying `/v1/*` and `/api/*` to `app` | React 19 · Vite 7 · TS 5.x · Tailwind 4 (npm) | **User decision, 2026-08-09, superseding ADR-0034.** Node never runs in production, so ADR-0033 stays at **7 services**; one Caddy origin keeps ADR-0029's cookie same-origin, so ADR-0022's revocation, the no-JWT rule and the absence of CORS all survive untouched. Path routing lives in Caddy's config, not in a FastAPI route-ordering rule that could shadow ADR-0050's `/v1` mount | **ADR-0052** (supersedes ADR-0034) | Next.js with a Node server (an 8th container and a 2nd runtime against A-012's *"no dedicated ops"*; ADR-0034's *"SSR/RSC/route-handlers/image-opt are all irrelevant or duplicative here"* survives the reversal); React via ESM with no build (keeps *"no Node"* literally true and forfeits the ecosystem that motivated the request); assets served by FastAPI `StaticFiles` (a catch-all fallback registered before the gateway mount silently returns HTML to a consumer's OpenAI SDK); assets in a named volume (UI and API version independently — a rollback serves the old SPA against the new API) |
| **ML stack** | `n/a` | — | Prope trains and serves no models. It forwards calls to workspace-configured upstream providers (A-024, A-094); the only "AI" surface is A-036's proposed fallback answer, which is a human-accepted revision | — | — |

### Deployment sizing (ADR-0033)

**4 vCPU · 8 GB RAM · 80 GB SSD · 2 GB swap.** Steady-state memory is ~2.7–3.1 GB across the seven
services plus the OS; 4 GB runs but leaves ~1 GB of page cache for PostgreSQL, which is where the
difference is felt. PostgreSQL tuned off its 128 MB default: `shared_buffers=1GB`,
`effective_cache_size=4GB`. Every service carries a `mem_limit`.

**Two tables grow without bound, and only one of them has a delete path.** `ledger.call_body` is roughly
3 GB/month at 10k calls/day, held at that by A-040's placeholder 30-day retention and A-132's chunked
`DELETE`; a disk-usage alert sits beside A-106's oldest-body gauge. **`evaluation.case_result` has no
retention setting and no expiry job at all** — it grows with review activity forever, ~1 GB at the
pilot's shape (**A-137**, found during evaluation's pass, which corrected this paragraph's earlier claim
that `call_body` was the only such term). Retention for stored eval outputs is OQ-013's to answer, not
step 4's.

**Metric label cardinality is bounded** (ADR-0030): closed-set values only. A `call_id`, `version_id`,
`session_id` or `consumer_key` is never a label.

### Two images, seven services (ADR-0031, ADR-0033, ADR-0052)

`prope-app` carries `app` and `worker` from one build, different commands. **`prope-web` is `FROM caddy:2`
with the Vite output baked into `/srv`** — so `caddy` is a built artefact rather than a stock image, and
the deploy pulls two tags. The host still pulls and never builds. Baking rather than volume-mounting is
deliberate: the SPA and the API then roll back together, which is what keeps ADR-0031's *"the tested
artefact is the deployed one"* true for the frontend as well as the backend. The one case it does not
cover is a **browser tab already open across a deploy** — outside the pipeline's reach, recorded as
**A-141**.

### Global conventions inherited from step 1

These are not step-4 decisions; they are recorded here so a per-module pass does not re-open them.

- **A-045** — ULID identifiers, one error envelope, cursor pagination, `/healthz` + `/readyz`.
- **A-046** — structured JSON logs, `prope_<module>_<name>_<unit>` metrics, and the content rule: no
  prompt body, fallback answer, request/response body, credential, eval output, or `prope.variables`
  **value** in a log line, metric label, or history event. Variable *names* may be logged.
- **A-003** — all timestamps RFC 3339 UTC.
- **A-128** — SQLAlchemy 2.0 async + Alembic + asyncpg; raw SQL for the gateway resolve read and
  A-118's `visible_subject_filter`.
- **A-127** — LangChain and LangGraph removed.

**Caching default: none.** Every cache in Prope is argued for individually — ADR-0012 (expires, nothing
invalidates), ADR-0022 (nothing cached, revocation lands next request), A-025 (60 s credentials),
ADR-0038 (process lifetime, no invalidation). A per-module `Cache` row therefore reads `n/a` unless the
module has an ADR of its own. **Four caches exist and none of them is ever invalidated** — four modules
reached that answer independently, which is why release-control's pass declined to break the pattern for
the case with the largest headroom (ADR-0012, second amendment).

**Backup/DR** is set by **ADR-0036** for the whole instance — nightly `pg_dump -Fc` copied to a second
group-controlled machine, 30-day retention, RPO 24 h / RTO ~10 min, `.env` to a different destination
(ADR-0032). Established during property-history's pass, which ADR-0033 named as its home. What varies
per module is tolerance, not mechanism. **A-131** records that the second machine may not exist yet.

**Two tables are excluded from the dump, for unrelated reasons, and both are `--exclude-table-data` so a
restore yields an empty table rather than a missing one**: `ledger.call_body` (ADR-0039 — including it
would silently extend a 30-day retention promise to 60) and `access.session` (ADR-0044 — including it
would silently undo ADR-0022's revocation promise). The pattern is that **the dump is a second lifecycle
for every table in it**, and a module's pass is where that gets checked.

**Tenant coverage is deny-by-default** (**ADR-0045**, replacing ADR-0035's enumeration rule). The CI
test walks **every** table in the eight module schemas: each must carry `workspace_id` with RLS enabled
and a policy, or appear in `GLOBAL_TABLES` with a written reason. Four entries qualify today —
`access.user`, `access.role_permission`, `history.history_action_registry`, and `access.workspace`
(policied on `id`, since it *is* the tenancy root). The old rule found a table only if it already had
the column, which meant three consecutive module passes each discovered a child table it could not see:
`call_body`, `prompt_grant`, `credential`. **`SECURITY DEFINER` functions are the only sanctioned policy
bypass, and there are four**: ADR-0042's `access.lookup_session` and `access.lookup_api_key`, ADR-0049's
`evaluation.claim_next_run()`, and ADR-0051's `access.list_workspaces()`. All four exist for one reason —
a read that must run *before* a tenant is known, because it is what produces the tenant. All four are
owned by `prope_migrate`, have an empty `search_path`, are `REVOKE`d from `PUBLIC`, and **return only
identifiers — never rows**, because a row-returning bypass performs the actual read with the policy off.
The fourth is deliberately generic so the set stops growing: one enumerator serves every cross-tenant
background job. A test asserts the set is exactly these four, and that assertion only means something
while the number tracks architecture rather than feature count.

**Three database roles** (ADR-0027 as extended by **ADR-0037**): `prope_app` writes at runtime and is
RLS-subject; `prope_migrate` changes structure and is the only role that can alter or remove a history
row; `prope_report` is `LOGIN` + `BYPASSRLS` + `SELECT`-only, for humans running cross-workspace reads
(A-126's Success metrics). No application code uses the third.

## Per-Module Stack

Stage 2 fills one module per pass, in the confirmed order above. Each module gets a row for every
per-module concern — Language, Web framework, Database, Cache, ML stack, Backup/DR — with `Inherited`
citing the baseline ADR, `Deviated` citing a new ADR written in the same pass, or `n/a` with a one-line
reason. No blank cells.

### property-history

The module that decided the database topology for everyone else. ADR-0023 puts `append()` on the
caller's connection inside the caller's open transaction, and a transaction does not span two databases
— so database-per-module was ruled out before step 4 opened. It has **no process, no route, and no
dependencies**; it is a library imported by `app` and `worker`.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline. Imported as a library by `app` and `worker` from the same image; no runtime of its own | ADR-0026 |
| **Web framework** | **`n/a`** — mounts no HTTP surface | — | `—` | No route, not even `/healthz` or `/readyz` (A-123, ADR-0023). **Does not import FastAPI**, so a route cannot be mounted; AC-7 asserts it against the route table | ADR-0023 |
| **Database** | PostgreSQL, schema `history`. `prope_app` holds INSERT + SELECT on `history_event` and SELECT only on `history_action_registry` | 17.x | `Inherited` | This module is *why* the baseline is one instance. ADR-0025's `REVOKE UPDATE, DELETE` and ADR-0035's policy both land on `history_event`; the RLS `WITH CHECK` is the half that matters here, without which `prope_app` could append an event into another workspace | ADR-0027, ADR-0025, ADR-0035 |
| **Cache** | The 31 registered actions, read into an immutable in-process mapping at process start. No TTL, no refresh, no invalidation | — | `Deviated` | Prope's default is no cache. The `p95 < 3 ms` append target already names this one, and its only refresh path is a deploy — ADR-0031 migrates *before* it restarts, so adding an action is safe by construction | ADR-0038 |
| **ML stack** | **`n/a`** | — | `—` | Trains and serves no models; it writes one table | — |
| **Backup / DR** | Nightly `pg_dump -Fc`, copied to a second group-controlled machine, 30-day retention. **RPO 24 h · RTO ~10 min** | — | `Inherited` | Mechanism established in this pass for the whole instance. A-121 makes this module its strictest consumer: with no retention setting and no expiry job, every row lost is lost permanently, and **a restore is the one operation that can un-write what ADR-0025 spent a privilege protecting** | ADR-0036, A-131 |

**Libraries**: SQLAlchemy 2.0 async on the *caller's* session, never its own (A-128, ADR-0023) ·
Alembic for the migration that creates the table, carries ADR-0025's grant and seeds the 31 actions ·
pydantic v2 for the per-action `details` allow-list (A-124) · `prometheus-client` + `structlog`
(ADR-0030) · ULID for `hev_` ids (A-045, ADR-0003). **Not FastAPI.**

**Deployment target**: none of its own. It ships inside the `app` and `worker` containers
(ADR-0026, ADR-0028, ADR-0033).

### call-ledger

The module three Stage-1 decisions all landed on at once, and the only one that deviates on more rows
than it inherits. It runs in **both** processes — the enqueue side and the HTTP surface in `app`, the
drain and the retention job in `worker` — sharing one writer implementation so pricing and `expires_at`
stamping cannot drift between them.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline | ADR-0026 |
| **Web framework** | FastAPI + uvicorn + pydantic v2 | ≥0.115 / ≥2.10 | `Inherited` | A real surface, unlike property-history: prices, the unpriced worklist, ceilings, retention, `/healthz`, `/readyz` | ADR-0026 |
| **Database** | PostgreSQL, schema `ledger`. The drain groups each batch by `workspace_id`, one `SET LOCAL` transaction per workspace | 17.x | `Deviated` | RLS is per-transaction and this is the **only cross-tenant batched writer in Prope**. `WITH CHECK` stays live where a mis-stamped `workspace_id` is most likely. `call_body` gains a `workspace_id` column so ADR-0035's CI test reaches it | ADR-0040 |
| **Cache** | **`n/a`** | — | `—` | Decided by ADR-0019, not by preference: cost is priced once and never revised, so a stale price row is a permanently wrong number with no correction path. The price table is read once per drain batch | ADR-0019 |
| **Async transport** | RabbitMQ durable queue, publisher confirms; **direct PostgreSQL write on a failed confirm**. No spill file | 4.x | `Deviated` | The only module whose durability claim (*100% of calls record a version ID*) outranks the broker's availability. Deletes a mechanism rather than adding one | ADR-0041 |
| **ML stack** | **`n/a`** | — | `—` | Records usage; produces none | — |
| **Backup / DR** | Nightly `pg_dump -Fc` with **`--exclude-table-data=ledger.call_body`**. Metadata, prices, ceilings, spend totals included | — | `Deviated` | A whole-instance dump would extend body retention from 30 days to 60, and `oldest_body_age_seconds` reads the live table — it would report green throughout. Bodies are best-effort by declaration (A-037) with no reader (ADR-0018) | ADR-0039, ADR-0036 |

**No partitioning** on `call_body`; retention stays a bounded-chunk `DELETE` (A-132), with the honest
note that space returns to the table's free list rather than to the disk. `call_record` cannot be
partitioned at all — the partition key would have to enter the unique constraint, turning A-099's upsert
key from `call_id` into `(call_id, created_at)`.

**Libraries**: FastAPI + pydantic v2 · SQLAlchemy 2.0 async + asyncpg (A-128) · Alembic · **aio-pika**
(ADR-0028) · `prometheus-client` + `structlog` · `python-ulid` — noting the `cal_` id is generated by
the **caller** at request time, not here (A-099).

### access-control

The module every other module calls, and the only one that owns tables the tenant model does not fit.
Six of its eight tables sit cleanly under ADR-0035; the other two are the tenancy root itself and the
grant table, and **two of its reads run before tenant context exists because they are what produces it**.
It inherits more rows than any module so far and deviates on the three that touch a credential.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline | ADR-0026 |
| **Web framework** | FastAPI + uvicorn + pydantic v2 | ≥0.115 / ≥2.10 | `Inherited` | 19 routes — the largest HTTP surface of any PLATFORM module, and the only one serving an unauthenticated path (`/auth/login`) | ADR-0026 |
| **Database** | PostgreSQL, schema `access`. RLS on the four `workspace_id` tables, on **`prompt_grant`** once it gains the column, and on **`workspace` via `id`**; the authentication bootstrap escapes through two `SECURITY DEFINER` functions | 17.x | `Deviated` | `session` and `api_key` are read *before* `app.workspace_id` exists — they produce it. The escape is two owned functions returning only an identity tuple, `REVOKE`d from `PUBLIC` with an empty `search_path`, not an exemption list and not a permissive policy | **ADR-0042** |
| **Cache** | **`n/a`** | — | `—` | Not the project default — ADR-0022 decided it against five alternatives. Nothing here is cached **and no caller may cache an answer**, which is the mechanism behind immediate revocation. The strongest `n/a` in the build | ADR-0022 |
| **Password hashing** | argon2id via `argon2-cffi`, **`m=47104` KiB · `t=1` · `p=1`**; in-process sliding-window limiter, checked *before* the hash | argon2-cffi ≥23.1, **pinned** | `Deviated` | ADR-0021 chose the primitive and never set the cost, so the lock's "don't tune it down" failure mode guarded nothing. `p=1` not the library's `4`: A-130 puts this in the gateway's process on 4 vCPU | **ADR-0043** |
| **ML stack** | **`n/a`** | — | `—` | Answers permission questions from a `(role, action)` table. Trains nothing, serves nothing | — |
| **Backup / DR** | Nightly `pg_dump -Fc` with **`--exclude-table-data=access.session`**. Users, workspaces, memberships, bindings, the role matrix, grants and keys all included | — | `Deviated` | A restore must not resurrect a signed-out session. Universal re-authentication becomes a property of the artifact rather than a runbook step taken during the worst hour the system has | **ADR-0044**, ADR-0036 |

**`prompt_grant` gains a `workspace_id` column.** It had none, so ADR-0035's CI test — which *"enumerates
tables carrying `workspace_id`"* — would have skipped the table implementing BR-01's private-by-default
grants. Same defect class ADR-0040 found on `call_body` one pass earlier, on a higher-liability table.
**ADR-0035's CI test also gains a second clause** so it reaches `workspace`, whose primary key *is* the
workspace id.

**What a restore does not fix (A-133)**: keys, grants, bindings and memberships revoked inside the 24 h
RPO come back, and the `history_event` rows recording those revocations roll back with them — so nothing
inside Prope can reconstruct what was lost. Accepted, with a procedural step recorded in A-133 and a
revisit trigger on OQ-006's sign-off.

**Libraries**: FastAPI + pydantic v2 · SQLAlchemy 2.0 async + asyncpg (A-128), with the two bootstrap
lookups and A-118's `visible_subject_filter` as raw SQL · Alembic for the schema, the policies, the two
`SECURITY DEFINER` functions and the `role_permission` seed · **`argon2-cffi`** (ADR-0021, ADR-0043) ·
`secrets` + `hmac.compare_digest` from the standard library for the consumer-key hash and its
constant-time comparison — deliberately *not* argon2, per ADR-0021 · `prometheus-client` + `structlog`
(ADR-0030) · `python-ulid` for `wsp_`, `usr_`, `key_` (A-045, ADR-0003).

**Deployment target**: the `app` container only. Nothing in this module runs in `worker` — it answers
questions, and no asynchronous work asks one (ADR-0026, ADR-0033).

### provider-access

Prope's **only outbound internet egress** and **the only module that decrypts anything**. It is also the
first module to run in `app` and `worker` for a reason other than sharing a writer: it dispatches
interactive traffic from one and batch traffic from the other, and that split turned out to be the
thing that fixed ADR-0016 rather than a detail of packaging.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline. Runs in **both** containers — interactive dispatch in `app`, batch dispatch in `worker` | ADR-0026, ADR-0028 |
| **Web framework** | FastAPI + uvicorn + pydantic v2 | ≥0.115 / ≥2.10 | `Inherited` | The provider dashboard's management API. `/readyz` stays gated on KEK availability, which is the one readiness check in Prope that is not about the database | ADR-0026 |
| **Database** | PostgreSQL, schema `provider`. **`credential` and `model_catalogue` gain `workspace_id`**; all three tables policied | 17.x | `Deviated` | `credential` carried no tenant column, so ADR-0035's enumeration skipped **the table holding every provider secret in Prope**. Third instance in three passes — so the rule inverts rather than the instance being patched | **ADR-0045** |
| **Cache** | Decrypted credentials, 60 s process-local, never persisted, never logged | — | `Deviated` | **No new ADR — A-092 and ADR-0014 already decided this.** What changed is that it now exists in *two* processes; A-092's ≤ 60 s rotation promise holds unchanged, because each TTL expires independently and neither is ever invalidated (the same reasoning as ADR-0012) | A-092, ADR-0014 |
| **Upstream HTTP client** | `httpx` async, custom transport connecting to the **validated resolved address**, hostname kept for SNI and certificate verification, redirects disabled | httpx ≥0.27 | `Deviated` | The only shape in which the promised dispatch-time SSRF check actually holds — otherwise the client re-resolves and the window reopens. Also satisfies A-088's exactly-one-attempt by construction and keeps responses raw, which AC-9 requires | **ADR-0047** |
| **Concurrency control** | `interactive_concurrency` in `app`, `batch_concurrency` in `worker`; plain local semaphores, sum is the provider budget | 24 / 8 (A-134) | `Deviated` | ADR-0028 put batch in `worker` and left interactive in `app`, so ADR-0016's process-local semaphore bounded neither — 32 silently became 64 against one key | **ADR-0046** |
| **ML stack** | **`n/a`** | — | `—` | Forwards calls to the workspace's own provider under BYOK. Prope holds no provider account and trains nothing | — |
| **Backup / DR** | Nightly `pg_dump -Fc`, **no exclusions** | — | `Inherited` | The dump carries ciphertext only, and ADR-0032/ADR-0036 send `.env` to a **different destination on a different schedule** — so AC-2 (*"the entire database and no other material yields nothing"*) holds through the backup channel. Asserted in the restore rehearsal, not assumed | ADR-0036, ADR-0032 |

**The KEK finally has an operational story.** ADR-0032 settled where it lives; **A-135** gives
`credential.kek_version` its meaning — `.env` may hold several `PROPE_KEK_V<n>`, the highest wraps, and
a rotation is *add V2 → re-wrap every `wrapped_dek` → remove V1*, with the plaintext credential never
touched. That is cheap only because ADR-0014 chose envelope encryption.

**Backup caveat worth carrying**: A-131 records that the second machine may not exist yet, in which case
the dump is copied by hand. If `.env` travels on the same medium as that dump, envelope encryption
becomes decorative in the backup channel — ADR-0032's *"different destination"* is a security control,
not filing preference.

**Libraries**: FastAPI + pydantic v2 · SQLAlchemy 2.0 async + asyncpg (A-128) · Alembic · **`httpx`**
for all upstream calls (ADR-0047) with hand-written SSE parsing on the 1 ms-per-chunk budget ·
**`openai` SDK as a *test-only* dependency** — the oracle for AC-9's contract assertion, deliberately
never the client · `cryptography` for AES-GCM envelope encrypt/unwrap (ADR-0014) ·
`prometheus-client` + `structlog` with the allow-listed upstream-error redaction (A-046) ·
`python-ulid` for `prv_`, `crd_`, `mdl_` (A-045, ADR-0003).

**Deployment target**: both `app` and `worker`, from the shared image (ADR-0026, ADR-0028, ADR-0033).
The container it runs in **is** the priority class it serves, which is what ADR-0046 relies on.

### prompt-registry

The largest module in the map and the one every other points at — and, on the stack, the one that
**inherits most**. Six of seven rows are the baseline. Its HTTP surface runs in `app`; its read
interface is imported by `worker`, because evaluation's batch runs read revisions there. It owns the
asset the product exists to hold, which is what makes its Backup/DR row the strictest in the build
despite being inherited unchanged.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline. HTTP surface in `app`; the read interface is imported by `worker` for evaluation's batch runs | ADR-0026, ADR-0028 |
| **Web framework** | FastAPI + uvicorn + pydantic v2 | ≥0.115 / ≥2.10 | `Inherited` | 10 routes plus `/healthz` and `/readyz`, and 5 internal in-process interfaces — the widest surface in the build | ADR-0026 |
| **Database** | PostgreSQL, schema `registry`. **`revision` gains `workspace_id`**; both tables policied | 17.x | `Inherited` | Fourth child table in five passes carrying only a parent FK — and the first one caught with **no new decision**, because ADR-0045 inverted the rule one pass earlier. That is the rule paying for itself | ADR-0027, **ADR-0045** |
| **Search index** | `pg_trgm` GIN over a trigger-maintained `prompt_property.search_text`; `ILIKE '%term%'` | contrib, bundled with PG 17 | `Deviated` | A-013 says *"substrings"*, not words. `tsvector`'s parser reads `namespace/name` as a file path — so `refund` would miss `support/refund-classifier`, the most likely query in this product. **OQ-010 answered 2026-08-09 and it strengthens this row rather than reversing it**: PostgreSQL ships no Vietnamese stemming dictionary, and Vietnamese words are multi-syllable with spaces, so word-based `tsvector` matching would be weaker here than in English while substring matching is unaffected. **A-150** folds diacritics and case inside the existing trigger — `unaccent()` is STABLE, so it cannot go in the index expression | **ADR-0048**, A-150, ADR-0053 |
| **Cache** | **`n/a`** | — | `—` | The lock's 5-minute catalogue cache is **deleted**: it cached a local table read *in its own process*, and would have existed twice once `worker` imports this module — the shape that broke ADR-0016. Nothing here is cached, so the gateway's 30 s TTL stays the only staleness in the read path | ADR-0026, ADR-0046, ADR-0012 |
| **ML stack** | **`n/a`** | — | `—` | The one module where a vector store would live if one existed. `00_context.md#scope` puts *"LLM-judge quality scoring; semantic/vector search"* out, OQ-001 holds it there, and A-013 records the retrofit as additive | A-013, ADR-0048 |
| **Backup / DR** | Nightly `pg_dump -Fc`, **no exclusions** | — | `Inherited` | The strongest claim on the dump in the build: `revision` **is** the asset. **A-136** records what the 24 h RPO costs here — unlike `call_body` (no reader) or `session` (log in again), a prompt body has no second source | ADR-0036, **A-136** |

**`revision` gains a `workspace_id` column.** Its fields were `version_id, prompt_id, revision_number,
body, …` — a child table reachable only through its parent, on the table holding **every prompt body in
Prope**. Under ADR-0035's old enumeration it would have been the fourth consecutive pass to discover one
of these by hand. Under ADR-0045 it is a coverage-test failure on day one and a one-line migration. No
ADR, because no decision was required — which is the outcome ADR-0045 was written to produce.

**What search actually does.** Substring, case-insensitive, matching inside words and inside model
names: `thentic` finds *"authentication helper"*, `refund` finds `support/refund-classifier`. No
stemming, so `contract` does not find `contracts`. **Body matches are the latest revision only** — the
corpus is bounded at 1,000 rows and ~32 MB by A-050 rather than 20,000 rows and 640 MB — but **every
revision's change summary is indexed**, all twenty of them, because A-050 caps a summary at 200
characters and twenty is ~4 KiB. That recovers the historical recall (*"which prompt did we change for
the refund thing"*) at 0.6% of the cost, in human-written text. Terms under three characters fall back
to a scan of 1,000 rows. Ordering is `updated_at DESC`; there is no ranking function in the MVP.

**Three filters stack in one statement** and none substitutes for another: RLS supplies the workspace
boundary invisibly (ADR-0045), A-118's `visible_subject_filter` supplies the within-workspace permission
filter in SQL, and `ILIKE` supplies the keyword.

**The column is maintained by a trigger, not by the application**, because drift is silent and wrong in
the unsafe direction — a body edited without its `search_text` rewritten makes the prompt un-findable by
its own new text, with no error and no metric. Sixth time this project has declined an
application-maintained invariant for that shape. `revision` stays append-only: the trigger fires on its
insert and writes `prompt_property`, which was already mutable (ADR-0002 untouched).

**`search_text` must never appear in an API response.** It is a second copy of the prompt body sitting
on the table every list endpoint reads, so a `SELECT *` on the list path would return every body in a
list payload. Named as a security requirement and an owed acceptance criterion; it extends OQ-006's
classification question and A-046's never-logged rule to a second column.

**The enrichment question was asked and answered in this pass.** An LLM keyword-extractor or summariser
on every save, and a vector store, were both rejected for the MVP — out of scope by declaration, and
architecturally because it would put a model on the *write path of the register*, spend the workspace's
own BYOK credential on a call they did not ask for, send every body upstream at save time including
drafts and retired prompts, and index the register on a model's non-deterministic opinion. ADR-0048
records the full argument and an ordered upgrade ladder — `simple`-dictionary `tsvector`, then
`pg_trgm` similarity ranking, then `pgvector` computed in `worker` on a schedule and never on the save
path — so the next person to ask finds an answer rather than reaching for a vector store.

**Libraries**: FastAPI + pydantic v2 · SQLAlchemy 2.0 async + asyncpg (A-128), with the `resolve()` read
and A-118's `visible_subject_filter` as raw SQL · Alembic for the schema, the RLS policies, BR-03's
released-pointer constraint, `CREATE EXTENSION pg_trgm`, the GIN index and the `search_text` trigger ·
stdlib **`difflib`** with `SequenceMatcher(autojunk=False)` for A-015's line diff — `autojunk` silently
discards lines appearing in over 1% of a sequence longer than 200 elements, which on a 32 KiB body with
repeated short lines yields a diff that looks *wrong* rather than slow; AC-2 already asserts 300 ms with
both bodies at the cap, so the cost of disabling it is under test · `prometheus-client` + `structlog`
(ADR-0030) · `python-ulid` for `prm_` and `rev_` ids (A-045, ADR-0003).

**Deployment target**: the `app` container for the HTTP surface, and the shared image's `worker` for the
read interface evaluation imports (ADR-0026, ADR-0028, ADR-0033). It has **no scheduled job and no queue
consumer of its own** — which is exactly why the Cache row is `n/a` rather than a deviation.

### evaluation

The module carrying the project's oldest unreconciled assumption: A-054 said *"asynchronously in-process
at concurrency 5"*, written when A-012 said there was one process, and ADR-0028 removed that premise
during Stage 1. This pass rewrote it. Evaluation runs in **both** containers — nine routes and
`get_review_summary` in `app`, the claim loop, the executor and the sweeper in `worker` — and it is the
**first module to run in `worker` without touching RabbitMQ**.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline. HTTP surface in `app`; claim loop, executor and sweeper in `worker` | ADR-0026, ADR-0028 |
| **Web framework** | FastAPI + uvicorn + pydantic v2 | ≥0.115 / ≥2.10 | `Inherited` | 9 routes plus `/healthz` and `/readyz`, and one internal interface release-control pulls (`get_review_summary`, A-042) | ADR-0026 |
| **Database** | PostgreSQL, schema `evaluation`. **All four tables gain `workspace_id`**; all four policied | 17.x | `Inherited` | First module where *every* table lacked the tenant column. No ADR and no decision — ADR-0045 makes it a coverage-test failure and a four-line migration | ADR-0027, **ADR-0045** |
| **Run execution** | Table claim — `worker` polls `eval_run` at 1 s with `FOR UPDATE SKIP LOCKED`, admission checked inside the claim transaction. **No broker message** | — | `Deviated` | RabbitMQ redelivery is a liability here: an unacked message on a crash re-dispatches paid cases, against AC-7 and A-054's *"costs a new run"*. Acking on receipt forfeits everything the broker was chosen for and leaves a second queue | **ADR-0049** |
| **Cache** | **`n/a`** | — | `—` | Nothing is cached. The assertion registry (A-061) is code, not state; a revision is read once per run through an in-process import; baseline *reuse* (ADR-0004) is a pairing rule pinned by identity, which is the opposite of a cache — a changed released pointer invalidates it structurally | ADR-0004, A-061 |
| **ML stack** | **`n/a`** | — | `—` | The module where an LLM judge would live, and the one place the context file names it out. Pass/fail comes only from deterministic assertions; *"an agent that writes its own tests and then reports that they pass is not evidence"* | A-005, A-043 |
| **Backup / DR** | Nightly `pg_dump -Fc`, **no exclusions** | — | `Inherited` | Counts live on `eval_run`, evidence on `case_result`. `--exclude-table-data` empties the child, so a restore renders "18 of 20 passed" with nothing behind it — wrong rather than empty. None of ADR-0039's three supports transfer | ADR-0036, **A-137** |

**All four tables gain a `workspace_id` column** — `eval_suite`, `eval_case`, `eval_run`, `case_result`.
Every one was a child reachable only through a parent, and this is the first module where *none* of them
had it. The running tally is **eight tables in six passes**; under ADR-0035's old enumeration this pass
alone would have been four hand-discoveries. It is now a CI failure and a migration, with no ADR, which
is the outcome ADR-0045 exists to produce.

**And the coverage column turned out to be load-bearing for the scheduler.** ADR-0049's claim query
counts a workspace's `running` runs to decide admission — `WHERE r2.workspace_id = r.workspace_id`.
Without that column the count joins back through `prompt_property` on every 1 s tick. The security rule
and the admission gate arrived at the same column independently, in the same pass.

**Why a claim and not a message.** `eval_run.status` is already a queue; a broker message beside it is a
second queue for one workload and the two can disagree in both directions. Worse, redelivery of an
unacked message on a worker crash re-dispatches every case — spending the workspace's own BYOK key on a
run nobody requested, which AC-7 forbids and A-054 explicitly chose against. This is workload-specific
and not a reversal of ADR-0028: call-ledger's drain has the opposite shape — a write that must not be
lost, idempotent on `call_id` (A-099), free to repeat — so redelivery is a feature there and a bill here.

**The claim is Prope's third `SECURITY DEFINER` function, and the first added since ADR-0042.** Found
while writing the block rather than while grilling it: `worker` polls `eval_run` across every workspace
to find work, and deny-by-default RLS correctly returns zero rows for that. A queued run's workspace is
not known until the claim, **because the claim is what produces it** — ADR-0042's own sentence about
sessions, transplanted unaltered. `evaluation.claim_next_run()` is built to that ADR's template: owned by
`prope_migrate`, empty `search_path`, `REVOKE`d from `PUBLIC`, and returning five identifiers and no
content. `worker` then `SET LOCAL app.workspace_id` and runs the revision read, the dispatch, the pricing
and the `case_result` writes under ordinary policy. The general form is worth knowing before `gateway`
and `release-control`: **a background worker that discovers its own work across tenants needs the same
escape an authentication bootstrap needs.**

**A-063 splits and shrinks.** Its dispatch clause (*"at most 10 across all runs of one workspace"*) is
deleted, superseded by ADR-0046's `batch_concurrency` of 8, which now sits in the same process. What
survives is `max_concurrent_runs = 2` per workspace, and it survives for **measurement, not throughput**:
wall-clock is identical either way, but the 120 s Success target is stated per suite and the metric is
labelled per run, so five interleaved runs each record the whole submit's duration and miss on all five.
Three bounds now do three different jobs — 5 dispatches within a run (A-054), 2 runs per workspace
(A-063), 8 dispatches per provider config (ADR-0046, A-134) — and **nothing bounds `worker` itself**,
recorded as **A-138** rather than guessed at.

**ADR-0046 is confirmed rather than reopened.** Its written dependency — *"this depends on evaluation's
pass landing batch dispatch in `worker`"* — held. One asymmetry surfaced in passing: ADR-0049's bound is
a database predicate inside the claim transaction and stays correct under a replicated `worker`;
ADR-0046's is a process-local semaphore and does not. A `worker` replica and a process-level cap are the
same conversation, in that order.

**A user-authored regex can hang the whole `worker` container.** A-005's eight assertion types include
regex, and the pattern is written by the prompt owner. Stdlib `re` has no timeout and holds the GIL in C
without yielding, so one catastrophic-backtracking pattern stalls not just its eval case but call-ledger's
drain, call-ledger's retention job and provider-access's batch dispatch alongside it. The **`regex`**
module with `timeout=1.0` per evaluation, plus a bound on input length, is used instead — a library
choice recorded here rather than as an ADR, with a failure mode and an acceptance criterion owed.

**AC-9 and AC-10 are owed restatements.** AC-10 asserts *"a global concurrency bound of 10"*, a number
ADR-0049 deletes. AC-9's modality refusal and A-029's spend-ceiling check both move to claim time, so a
202 now precedes them — both are checked **twice**, advisory at `POST` for a fast error and authoritative
at claim, since a queued run may sit behind others that consume the budget while it waits. Only the
claim-time result writes `status=refused`.

**Libraries**: FastAPI + pydantic v2 · SQLAlchemy 2.0 async + asyncpg (A-128), with the `FOR UPDATE SKIP
LOCKED` claim as raw SQL · Alembic for the schema, the RLS policies on all four tables,
`evaluation.claim_next_run()` with its grants, and the `(workspace_id, status)` index the claim reads · **`regex`** with `timeout=1.0` for A-005's regex
assertion, deliberately not stdlib `re` · **`jsonschema`** for A-005's JSON-schema assertion — pydantic
v2 *emits* JSON Schema but does not validate against an arbitrary one, so this assertion type had no
library until now · `prometheus-client` + `structlog` (ADR-0030), with `suite_name` as a log field and
never a metric label · `python-ulid` for `evs_`, `evc_`, `evr_`, `evcr_` (A-045, ADR-0003).
**Not `aio-pika`** — the first module in `worker` that does not consume.

**Deployment target**: `app` for the nine routes and `get_review_summary`; `worker` for the 1 s claim
loop, the run executor at concurrency 5, and the sweeper's startup pass and 60 s timer (ADR-0026,
ADR-0028, ADR-0033, ADR-0049).

### gateway

The tightest budget in the build, and the only module that owns **no table and no durable data** — so it
is the first with `n/a` on both the Database and the Backup/DR rows, and the first where ADR-0045's
coverage walk finds nothing at all. Its entire state is a cache that is *"correct to rebuild empty at any
moment"*. It runs in `app` only: nothing here is deferrable, because the one asynchronous act — handing
a record to call-ledger — happens in this process after the response is flushed.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline. `app` only — no `worker` presence | ADR-0026 |
| **Web framework** | FastAPI — **two application objects in one process**. The gateway is a standalone ASGI app with its own exception handlers, middleware and schema, mounted by the management app at `/v1` | ≥0.115 / ≥2.10 | `Deviated` | The only surface exempt from ADR-0003's error envelope (A-026, A-045), and Starlette scopes handlers **per app, not per route**. A shared handler sends the management envelope to a consumer's SDK; a shared 422 breaks it on the first integration attempt | **ADR-0050** |
| **Database** | **`n/a`** — owns no table | — | `—` | `data.owns` is `table: none`. Reads go through prompt-registry's and access-control's in-process interfaces, never their tables — *"a direct read would create a second, weaker enforcement point beside the Approved-only database constraint"* | ADR-0027, ADR-0045 |
| **Cache** | Bounded LRU, 5,000 entries, **TTL 30 s**, keyed `(workspace_id, model_name, pin)`. Nothing invalidates it. **Stale-if-error deleted** | — | `Deviated` | **No new ADR — ADR-0012 already decided this and is amended rather than replaced.** The only cache in Prope with a TTL, and the only staleness left in any read path | **ADR-0012** (amended) |
| **ML stack** | **`n/a`** | — | `—` | It does not even choose the model: A-024 puts provider, model and parameters on the revision and forbids the caller overriding them. It composes and forwards | A-024, A-043 |
| **Backup / DR** | **`n/a`** — owns no data | — | `—` | First `n/a` on this row in the build. A restore restores nothing of the gateway's, which is the strongest form of the property A-136 and A-137 had to argue for | — |

**Stale-if-error is deleted, and two of ADR-0012's three arguments went with it.** That ADR rejected
*"no cache at all"* because *"the database's availability becomes the gateway's availability"* — but
A-114 and ADR-0022 put **two uncacheable access-control reads ahead of the cache on every request**, so
that property was already spent. And stale-if-error's trigger, *"when prompt-registry is unreachable"*,
describes a state ADR-0026 removed: prompt-registry is an in-process call, "unreachable" means the
database is unreachable, and authentication fails on it first. Gone with the window:
`prope_gateway_stale_resolution_total`, the `GatewayStaleResolution` **page**, the `cache=stale` label,
one failure mode, one risk row, and a chaos test that cannot be performed. The precedent is ADR-0041's
own words about the spill file — *"a path that only runs during an incident is a path nobody has watched
work."*

**What the cache now rests on is latency and nothing else** — a fifth of a 50 ms budget A-031 calls a
placeholder. Deleting it outright was seriously considered and rejected on asymmetry: being wrong about
30 s of staleness against a 5-minute restore target is recoverable, and being wrong about latency on a
path other products' production traffic depends on is an incident in someone else's product.

**This is the third mechanism in three consecutive passes found resting on a premise a later decision
had removed** — prompt-registry's catalogue cache, A-063's dispatch clause, and now stale-if-error. All
three were written while the architecture was still "services".

**Four stale references to the deleted spill file are corrected** — in `outputs`, in the
queue-saturation failure mode, in A-087's text, and in the chaos plan — and **AC-11 is owed a
restatement**, because it asserts an in-process queue filling and bodies being dropped first, which
ADR-0041 replaced with broker-publish-and-confirm plus an inline PostgreSQL fallback. The deletion also
left a gap nobody had stated: **a process killed between the flush and the publish loses that record and
nothing counts it**, because `metadata_dropped_total` needs code to run in order to increment.
Recorded as **A-139** rather than met by rebuilding a mechanism ADR-0041 removed on good grounds.

**A `gateway` schema is created and left empty.** ADR-0027 provisioned eight; this module needs none.
Creating it gives ADR-0045's walk a place to look, so a table added here later lands under the rule
rather than outside it.

**`/healthz` and `/readyz` stay on the management app while the gateway lives in `app`.** The gateway's
readiness condition is *"access-control and prompt-registry are reachable"*, and ADR-0026 makes both
in-process — so that sentence **is** *"the database is reachable"*, which ADR-0041 already has `/readyz`
report. Two pairs would be two names for one fact. They separate again on an A-130 split.

**A-130 is confirmed, with a sharper trigger and a corrected price.** ADR-0043 turned *"argon2id is
deliberately expensive"* into `m=47104` · `p=1`, a known ~46 MiB event inside a 50 ms p95 — and the
gateway is the only surface in `app` with a Success-metric budget at all. Against that, the split now
costs more than A-130 stated: ADR-0046's `interactive_concurrency` is process-local, and `app` keeps
A-090's provider verification probe, so a split needs a third cap column or leaves the probe uncapped.
**ADR-0050 restores the other half** — the gateway is already a standalone app object, so the split is
`uvicorn prope.gateway:app` with no code change, exactly as A-130 originally claimed.

**Libraries**: FastAPI + pydantic v2 as **two application objects** (ADR-0050) · uvicorn, one process
(ADR-0026, A-130) · Starlette's `StreamingResponse` for the relay, against A-038's per-chunk budget —
accumulation runs alongside and never delays a chunk · **no database driver of its own**: every read is
an in-process call into prompt-registry or access-control, and the only write path this process holds is
ADR-0041's fallback, which is call-ledger's writer function, not the gateway's ·
`prometheus-client` + `structlog` (ADR-0030), with A-046 extended here to `prope.variables` **values** ·
`python-ulid` for the `cal_` id the gateway generates at request time (A-099 — generated *here*, owned by
call-ledger). **No `httpx`** — every upstream call in Prope is issued by provider-access (A-043).

**Deployment target**: the `app` container, mounted at `/v1` behind Caddy's single ingress (ADR-0026,
ADR-0033, A-129, A-130). No `worker` presence.

### release-control

The eighth and last module, and the first to **inherit every standard row**. Its three tables already
carry `workspace_id`, so ADR-0045's walk changes nothing — the first module in the build that owns tables
and still needs no migration from it. What it deviates on is a concern the baseline never named: it is the
first module whose scheduled work must see **every workspace at once**, and deny-by-default RLS answers
that with zero rows.

| Concern | Choice | Version / Range | Status | Rationale | ADR |
|---------|--------|-----------------|--------|-----------|-----|
| **Language** | Python | pinned 3.13.x | `Inherited` | Baseline. 11 routes in `app`; one sweep job in `worker` | ADR-0026, ADR-0028 |
| **Web framework** | FastAPI + uvicorn + pydantic v2 | ≥0.115 / ≥2.10 | `Inherited` | 11 routes, one of them the composite review screen (diff + per-suite eval summary + decision controls). No `/healthz`+`/readyz` pair of its own — the gateway's pass collapsed those onto the one management app | ADR-0026 |
| **Database** | PostgreSQL, schema `release`. All three tables policied, **no column added** | 17.x | `Inherited` | `approval`, `release` and `review_task` each already carry `workspace_id`. First module in eight where the coverage walk changes nothing; the running tally stays at **eight tables in six passes** | ADR-0027, ADR-0045 |
| **Cache** | **`n/a`** | — | `—` | The strongest `n/a` on this row in the build: A-047 does not merely decline a cache, it forbids storing the composition, because *"a recomputed comparison would answer a different question later."* `approval.evidence_digest` is the anti-cache — stored **because** it must never be recomputed | A-047, A-074 |
| **Scheduled work** | One `asyncio` sweep in `worker` — gauges at 60 s, pointer reconciliation at startup and hourly. Enumerates tenants through **`access.list_workspaces()`**, then `SET LOCAL app.workspace_id` per workspace and reads under ordinary policy | — | `Deviated` | An unscoped sweep returns zero rows under ADR-0045, so `prope_release_review_task_overdue` would read `0` forever and `BreakGlassTaskOverdue` would never fire — with nothing indicating it was broken | **ADR-0051** |
| **ML stack** | **`n/a`** | — | `—` | Records human decisions. Nothing is scored, inferred, ranked or generated; ADR-0005 exists precisely to keep the eval advisory and the judgement human | — |
| **Backup / DR** | Nightly `pg_dump -Fc`, **no exclusions** | — | `Inherited` | These three tables *are* BR-04's audit claim, and the headline Success-metric SQL runs against them. `evidence_digest` holds counts, ids and money and never a model output — the only module that pre-empted OQ-013 rather than inheriting it | ADR-0036 |

**Withdraw is loud, but it is up to 30 seconds late — and six live claims said otherwise.** ADR-0009's
consequence read *"the gateway's 30 s resolution cache invalidates on withdrawal exactly as it does on
release"*; ADR-0012 replaced invalidation with expiry and the sweep was never finished. The other five:
this lock's `events.publishes` comment, its `forbidden_dependencies` reason for the gateway, its A-031
assumption line, ADR-0001's consequence, and A-041's reversibility note. Two of them are ADRs this module
consumes. The operational one is the withdraw failure mode's *"rises immediately"*, and **AC-7 asserts the
gateway returns model-not-found with no tolerance stated** — an e2e test whose result depends on cache
age, guarding the action that takes another product's feature offline.

**The broker rejection had to be re-made rather than inherited.** ADR-0012 rejected pub/sub invalidation
with an explicit caveat about its own reasoning — *"rejected by A-012 **before** it is rejected on
merit"* — and ADR-0028 removed A-012's no-broker clause during Stage 1. Re-argued on merit it loses
anyway: a fanout consumer would fire only on withdrawal, **the rarest action in the product**, which is
ADR-0041's *"a path nobody has watched work"* for the third time in three passes; it would make `app` a
broker consumer for the first time, inside the one process with a Success-metric latency budget; it would
not close the window under a restart or A-130's split; and four modules have independently chosen
TTL-or-nothing. **This is the pattern's fourth consecutive appearance and the first in a rejected
alternative rather than an adopted mechanism** — the more dangerous shape, because a rejection is read
only by whoever is about to re-propose it.

**ADR-0008 was a seam and is now a checked convention.** *"Release-control writes no table it does not
own"* was written against a service boundary. ADR-0026 gives one process and ADR-0027 gives one role, so
`prope_app` holds `UPDATE` on `registry.revision` no matter whose code is running — and that ADR named the
stakes itself: *"a module that can write the value the constraint checks can defeat the constraint by
writing it first."* The value is `Approved`; the constraint is **BR-03**. This is the **ninth
application-maintained invariant in the build and the first that could not be pushed into the database**.
The check is an `import-linter` layering contract in ADR-0031's job — each module package may import only
its own table models plus the declared interfaces of its dependencies — which is the same move as
ADR-0045's coverage test, ADR-0025's grant test, A-123's empty route table and A-124's allow-list. Its
honest limit is that it constrains imports, so it catches the ORM path and not a hand-written `text()`
UPDATE.

**Per-module roles were the obvious answer and are blocked by ADR-0023.** ADR-0027 had already parked
*"role per module"* as *"right idea, adoptable later"*. It cannot land here, for a reason older than
either: a transaction lives on one connection under one role, and ADR-0023 puts `append()` on the
**caller's** connection inside the **caller's** open transaction while ADR-0008 puts the status write and
the decision row in that same transaction. A nested `release-control → prompt-registry →
property-history` chain would need `SET ROLE` save-and-restore in application code with RLS re-evaluating
mid-transaction — an application-maintained invariant with no failure signal, which is the thing being
solved.

**The reconciliation query survives with a different job.** It was specified as *"the tripwire that
proves the assumption still holds after step 4 chooses the stack"* — and step 4 chose one process on one
database, so the orphaned-pointer scenario it covered **can no longer occur**; A-130's split does not
disturb it either, because the gateway is the process that leaves and release-control, prompt-registry and
property-history stay together. What it now detects is a released pointer written by something other than
a release: the residual exposure ADR-0008's amendment leaves. **CI catches the shape; the sweep catches
the instance.** Second time in three passes a mechanism survived for a different reason than the one it
was created for — A-063 was the first.

**The sweep's own failure is quiet, and that is recorded rather than fixed.** If the task dies the gauges
freeze at their last value rather than dropping to zero, so `BreakGlassTaskOverdue` neither fires nor
visibly breaks. A sweep-heartbeat counter is owed. **A-140** carries the cadence and the N+1-transactions
shape, unbounded in workspace count, against an **OQ-012 that has now been silent for five consecutive
passes**.

**Libraries**: FastAPI + pydantic v2 · SQLAlchemy 2.0 async + asyncpg (A-128) · Alembic for three tables,
their RLS policies, and `access.list_workspaces()` with its `REVOKE`/`GRANT` · a plain **`asyncio` task**
for the sweep, matching call-ledger's retention job and evaluation's sweeper — **no scheduler library
enters the build for a third timer** · **`import-linter`** as a CI-only dependency enforcing ADR-0008's
layering contract across all eight modules · `prometheus-client` + `structlog` (ADR-0030), with A-046
extended here to the free-text `reason`, `comment` and `acknowledgement_reason` — stored and rendered in
the property history, never in a log line · `python-ulid` for `apr_`, `rel_`, `rvt_` (A-045, ADR-0003).
**No `difflib`** — the diff is prompt-registry's `get_diff`, rendered here, not computed here.
**Not `aio-pika`** — the second module in `worker` that consumes nothing.

**Deployment target**: the `app` container for the 11 routes, and `worker` for the sweep (ADR-0026,
ADR-0028, ADR-0033, ADR-0051). Sixth module in `worker`, second one there with no broker involvement.

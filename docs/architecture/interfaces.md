# Interfaces

> **Status**: locked
> **Last updated**: 2026-08-20
> **Count**: 39 registered seams — 23 in-process, 1 broker queue, 12 management API, 3 external HTTP

Every seam that crosses a module boundary. Real specs are generated from the provider's code at build
time; this file pins the agreement — **who talks to whom, over what, authenticated how, with what
delivery and failure semantics, at what version.**

**Global conventions are [[A-142]]** (in-process meaning, failure crossing, timeouts, versioning, the
broker envelope, correlation, idempotency, auth per class), on top of **[[A-045]] / ADR-0003** (ULID
ids, error envelope, cursor pagination, `/healthz` + `/readyz`, RFC 3339 timestamps, not-found-never-
forbidden). Every block below inherits both and states only what is specific to it.

**Read A-142 §1 before implementing any `internal` row.** Twenty seams are Python calls inside whichever
container the caller runs in — `app` or `worker`, same image, different command. None is remote. Any
per-process state behind one of them exists **twice**.

---

## Registry

| INT | From -> To | Kind | Shape | Auth | Version | Notes |
|-----|-----------|------|-------|------|---------|-------|
| INT-001 | prompt-registry, prompt-conversion, release-control, evaluation, provider-access -> access-control | internal | `may(actor, action, subject)` | none (A-142 §8) | in-repo | Fails closed by raising. Closed action vocabulary; unknown action -> deny |
| INT-002 | prompt-registry, prompt-observation -> access-control | internal | `visible_subject_filter(actor, subject_type)` | none | in-repo | Set form pushed into the caller's own `WHERE`. **Fourth mode `namespaces` added 2026-08-18 (ADR-0061)** — it answers A-118's own revisit condition |
| INT-003 | gateway -> access-control | internal | `authenticate_api_key(secret)` | none | in-repo | Constant-time compare. Never cached, by either side |
| INT-004 | gateway -> access-control | internal | `may_resolve(key_id, model_name, namespace)` | none | in-repo | Default-deny. **Name scope OR namespace scope, union (ADR-0061)**. Refusal returns the same not-found shape as an unknown model |
| INT-005 | every module's management API -> access-control | internal | `authenticate_session(cookie)` | none | in-repo | A live row read, not a token verification. **Consumer is a shared dependency, not a module — see Unmatched pairs** |
| INT-006 | prompt-registry, release-control, evaluation, provider-access, access-control -> property-history | internal | `append(event)` | none | in-repo | **Runs on the caller's connection inside the caller's open transaction.** Raises; the raise is the mechanism |
| INT-007 | prompt-registry, release-control, provider-access -> property-history | internal | `read(scope, cursor, limit)` | none — caller has already checked | in-repo | Ordered by `seq` DESC, never by timestamp |
| INT-008 | CI route-table test -> property-history | internal | `registered_actions()` | none | in-repo | The 31-action vocabulary as data, so A-120's rename is checked rather than trusted |
| INT-009 | gateway -> prompt-registry | internal | `resolve(model_name, pin)` | none | in-repo | The hot path. Must distinguish *name unknown* from *nothing released* |
| INT-010 | gateway -> prompt-registry | internal | `list_released(workspace_id)` | none | in-repo | Backs `GET /v1/models`. No cursor, no filters, released only |
| INT-011 | evaluation, release-control -> prompt-registry | internal | `get_revision`, `get_released_revision`, `get_diff` | none | in-repo | Read-only. `get_diff` is `difflib` with `autojunk=False` |
| INT-012 | release-control -> prompt-registry | internal | `set_revision_status(version_id, status, decision_id)` | none | in-repo | Transition validated by the provider. The seam that keeps ADR-0008 true |
| INT-013 | release-control -> prompt-registry | internal | `set_released_revision(prompt_id, version_id, release_id)` | none | in-repo | The **only** write to the released pointer. Compare-and-set |
| INT-014 | release-control -> prompt-registry | internal | `clear_released_revision(prompt_id, release_id)` | none | in-repo | A separate command, not a NULL argument — no carve-out in the Approved-only constraint |
| INT-015 | gateway, evaluation -> provider-access | internal | `dispatch(...)` | none | in-repo | Exactly one attempt. Returns a typed `DispatchError`, never raises on upstream failure |
| INT-016 | prompt-registry -> provider-access | internal | `get_model_catalogue(provider_config_id)` | none | in-repo | Soft — degrades the picker, never refuses a save |
| INT-017 | release-control -> evaluation | internal | `get_review_summary(prompt_id, version_id)` | none | in-repo | Read-only pull. Evaluation never calls back |
| INT-018 | gateway -> call-ledger | **event** | queue `prope.call_record` | broker credentials from `.env` | envelope `schema_version: 1` | At-least-once, durable, publisher confirms. **Direct PostgreSQL write on a failed confirm.** DLQ `prope.call_record.dlq` |
| INT-019 | evaluation -> call-ledger | internal | `price_usage(run_id, usage_rows)` | none | in-repo | In-process, **not** the broker. Both sides run in `worker` |
| INT-020 | evaluation -> call-ledger | internal | `check_spend_ceiling(workspace_id)` | none | in-repo | **Fails OPEN**, counted. Never returns a figure |
| INT-021 | evaluation -> call-ledger | internal | `get_run_totals(run_id)` | none | in-repo | The two counts are part of the answer, not diagnostics |
| INT-022 | consuming product's SDK -> gateway | http | `POST /v1/chat/completions`, `GET /v1/models` | consumer API key, `Authorization` | `/v1` — OpenAI's, not ours | **20 concurrent per key**, OpenAI-shaped 429 (A-143). Errors are OpenAI-shaped, never the management envelope |
| INT-023 | provider-access -> the workspace's upstream provider | http | OpenAI-compatible chat completions + model list | the workspace's own credential | the provider's | **Only workspace-credential outbound egress.** Scheme allow-list, private-range refusal, redirects disabled |
| INT-024 | web SPA -> prompt-registry | http | `/api/v1/prompts…`, `/api/v1/revisions…` | session cookie | `/api/v1` frozen | 10 routes. Permission filtering in the repository layer via INT-002 |
| INT-025 | web SPA -> evaluation | http | `/api/v1/…/eval-suites`, `/api/v1/eval-runs…` | session cookie | `/api/v1` frozen | 9 routes. `POST eval-runs` returns 202 + one run id per suite |
| INT-026 | web SPA -> release-control | http | `/api/v1/…/submit`, `/approve`, `/releases…`, `/review-tasks…` | session cookie | `/api/v1` frozen | 10 routes. The product's decision surface; every write appends history in the same transaction |
| INT-027 | web SPA -> provider-access | http | `/api/v1/providers…` | session cookie | `/api/v1` frozen | 8 routes. **No field, parameter or flag returns a credential** |
| INT-028 | web SPA -> call-ledger | http | `/api/v1/prices…`, `/spend-ceiling`, `/retention` | session cookie | `/api/v1` frozen | 5 routes. Prices are append-only; no body read path exists |
| INT-029 | web SPA -> access-control | http | `/api/v1/auth…`, `/workspaces…`, `/grants`, `/keys`, `/permissions`, `/users/{id}/tombstone` | session cookie (except `/auth/login` and `/auth/register`) | `/api/v1` frozen | 27 operations across 23 paths as built — OQ-134 records that this count and the lock file's have disagreed since ADR-0052; ADR-0056 added two and ADR-0057 six. **5/email, 20/address per 15 min on login** (A-144); **10/actor, 10/address per 15 min on invite redemption** (ADR-0057) |
| INT-030 | compose healthcheck, operator -> every module with a process | http | `GET /healthz`, `GET /readyz` | none | `/` unversioned | Readiness differs per module and the differences are deliberate. property-history exposes neither |
| INT-031 | web SPA -> prompt-conversion | http | `POST /api/v1/prompt-conversions` | session cookie | `/api/v1` frozen | Explicit preview-only conversion through the app-owned Agent; never saves a revision |
| INT-032 | prompt-conversion -> prompt-registry | internal | `load_prompt(prompt_id)` | none | in-repo | Reads identity/ownership only to build the permission subject; registry never calls back |
| INT-033 | prompt-conversion -> app-owned OpenAI | http | structured Chat Completions | `APP_OPENAI_API_KEY` | provider's | Source is untrusted data; one repair; independently metered and circuit-broken |
| INT-034 | gateway -> prompt-observation | internal | `record_observation(...)` | none | in-repo | **Post-flush, never raises, never blocks** — INT-018's two properties, for INT-018's reason. Direct write, no second queue (A-155). Reached only on the forwarded path |
| INT-035 | web SPA -> prompt-observation | http | `/api/v1/observations…` | session cookie | `/api/v1` frozen | 7 routes. Every one checks `prompt.read` against the observation's **namespace** (ADR-0061); the proposal route **writes nothing** |
| INT-036 | gateway -> prompt-registry | internal | `list_namespaces(workspace_id)` | none | in-repo | **Which namespaces does this workspace use** — ADR-0062's entry rule. Here rather than in access-control because ADR-0020 forbids that module reading `registry.folder`. Cached 30 s by the caller |
| INT-037 | prompt-readiness -> prompt-registry | internal | `get_usage_profile(...)` on the property and the revision's stamped copy | none | in-repo | **Registry owns the column and readiness only reads it.** Declared, never inferred (A-163). An undeclared profile resolves to the conservative worst case rather than to NULL |
| INT-038 | web SPA -> prompt-readiness | http | `GET /api/v1/prompts/{id}/revisions/{vid}/readiness` | session cookie | `/api/v1` frozen | The card. `prompt.read`. **This read performs the freeze** — first call on a revision that has left `Draft` writes `readiness.report` once, idempotent under a unique constraint (ADR-0067) |
| INT-039 | web SPA -> prompt-readiness | http | `POST /api/v1/prompts/{id}/revisions/{vid}/probe` | session cookie | `/api/v1` frozen | Spends the workspace's provider credit. `probe.start`, the twenty-seventh action, seeded to Admin and Owner. Refuses `spend_ceiling_reached` **before** the first dispatch |
| INT-040 | web SPA -> prompt-readiness | http | `POST /api/v1/prompts/{id}/revisions/{vid}/case-drafts` | session cookie | `/api/v1` frozen | Drafts prompt-specific adversarial cases into the **library**, never onto the prompt's yardstick. `dataset.draft`, reused; nothing new minted |
| INT-041 | web SPA -> prompt-readiness | http | `POST /api/v1/prompts/{id}/readiness/dismissals` | session cookie | `/api/v1` frozen | `prompt.edit`. Per (workspace, prompt, rule_id), carried forward across revisions. A reason is required and no history event is written (ADR-0067) |
| INT-042 | web SPA -> prompt-readiness | http | `GET /api/v1/readiness/rules` | session cookie | `/api/v1` frozen | The closed rule catalogue and its version, so a client can render every code it might receive and CI can assert the `vi` catalogue is total over it (ADR-0053) |
| INT-043 | prompt-improvement -> prompt-registry | internal | `summarise_prompt_calls(prompt_id, window_start, window_end)` | none | in-repo | **ADR-0055's read path with a WINDOW on it, not a second path beside it.** Returns counts, never rows: the type has nowhere to put a call's identity, let alone a body. `source='gateway'` only, so a suite run cannot make "latency got worse" |
| INT-044 | prompt-improvement -> prompt-registry | internal | `list_released_prompts(workspace_id)` | none | in-repo | The sweep's worklist — prompts with something in production. Not `list_prompts` with arguments: that one will not run without a `VisibleFilter`, and this caller is the system inside `worker`, with no reader to filter for |
| INT-045 | web SPA -> prompt-improvement | http | `GET /api/v1/improvement/findings` | session cookie | `/api/v1` frozen | The inbox. `prompt.read`, authorised **per prompt** inside the route: a prompt the reader cannot see contributes no row, no count and no total that differs (A-116 at the list level) |
| INT-046 | web SPA -> prompt-improvement | http | `GET /api/v1/prompts/{prompt_id}/findings` | session cookie | `/api/v1` frozen | The per-prompt tab, beside ADR-0055's call-records tab. `prompt.read`. Returns dismissed and resolved findings too — this is the prompt's own degradation history, not a queue |
| INT-047 | web SPA -> prompt-improvement | http | `POST /api/v1/improvement/findings/{finding_id}/dismiss` | session cookie | `/api/v1` frozen | `prompt.edit`. A reason is required and **no history event is written** — dismissing a lint is not a state change on a prompt property (A-102, ADR-0067's line, unmoved) |
| INT-048 | web SPA -> prompt-improvement | http | `POST /api/v1/improvement/proposals/{proposal_id}/accept` | session cookie | `/api/v1` frozen | **Writes no revision** (ADR-0068 SR-6). Records the disposition, appends a history event, returns the candidate body. Declared `revision.create` anyway: handing over a body destined for a revision somebody could not create would be a permission gap wearing a read's clothes |
| INT-049 | web SPA -> prompt-improvement | http | `POST /api/v1/improvement/proposals/{proposal_id}/dismiss` | session cookie | `/api/v1` frozen | `prompt.edit`, and the ONE history action of the three that requires a reason. The per-detector dismissal rate is what would retire a detector, and a rate without reasons cannot tell a bad detector from a bad remedy |
| INT-050 | web SPA -> prompt-improvement | http | `PUT /api/v1/workspaces/{workspace_id}/improvement-schedule` | session cookie | `/api/v1` frozen | `spend_ceiling.manage`, because enabling the weekly re-probe commits the workspace to a recurring provider charge on its own credential — a spending decision before it is an authoring one |

---

## INT-001 — `may(actor, action, subject)`

**Provider**: access-control
**Consumers**: prompt-registry, prompt-conversion, release-control, evaluation, provider-access,
prompt-observation
**Transport**: in-process (A-142 §1)
**Auth**: none — the caller authenticated at its own edge
**Version**: in-repo

**Request carries**: `actor` = `{type: user | consumer_key, id, workspace_id}`; `action`, a string from
the closed vocabulary; `subject` = `{type, id, workspace_id, owner_id?, access_level?, namespace?}`.
**The subject's attributes are supplied by the caller**, from the row it has already read —
access-control may not read `prompt_property`, `revision`, `eval_suite` or `provider_config`, and the
reverse edge is forbidden (ADR-0020). This is what lets six modules depend on this one without a cycle.

**`namespace` added 2026-08-18** ([[ADR-0061]]), and it extends ADR-0020 rather than straining it for
one reason worth stating at the seam: `registry.folder` is **flat**. A namespace is one string with no
ancestors, so the oracle needs nothing beyond what the caller already holds. Under a nested folder
model the attribute would be a *path* whose meaning depends on rows this module may not read, and
ADR-0020's whole arrangement would collapse — which is why flat folders are now a constraint carrying a
reason rather than a shape awaiting improvement.

**Returns**: allow or deny. Nothing else — no reason string, no partial answer, no list.

**The action vocabulary is closed** ([[A-115]]). An unrecognised action is a **deny**, not an error,
because a typo that silently allows is the failure this closure exists to prevent. The four callers use:

| Caller | Actions |
|---|---|
| prompt-registry | `prompt.read`, `prompt.edit`, `prompt.create`, `prompt.retire`, `prompt.change_owner`, `prompt.change_access` |
| release-control | `revision.submit`, `revision.approve`, `release.create`, `release.break_glass`, `release.withdraw` — **five distinct permissions**, not one |
| evaluation | `suite.read`, `suite.edit`, `run.start`, `run.read` — `suite.edit` is distinct from `prompt.edit`, which is BR-10 expressed as data |
| provider-access | `provider.configure`, `provider.rotate_credential`, `provider.disable`, `catalogue.read` |

**Failure semantics**: **raises, and no caller catches it.** The caller's request becomes a 5xx in the
[[A-045]] envelope. This is how *"fails closed: an unavailable oracle must never become an allow"*
becomes true without any code asserting it — there is no `except` in which an allow could be
manufactured. A caller that wraps this call in a `try` has introduced the bug this seam is shaped to
make impossible.

**Not cacheable, by either side** ([[A-114]], ADR-0022). Revocation is effective on the next request,
and a cache is the mechanism that would make that false. This is a deliberate divergence from the 30 s
resolution cache sitting beside it at INT-009, and the reason is what a stale answer costs: a stale
pointer serves a previously approved revision one TTL late; a stale permission serves a revoked actor.

**Idempotency**: a pure read; retry is free.

**Refusal shape at the caller's edge**: forbidden-naming-the-permission when the actor can see the
subject, **not-found when they cannot** ([[A-116]], [[A-045]]).

**Spec**: generated from `access-control`'s Python signatures at build time -> in-repo type stubs.

---

## INT-002 — `visible_subject_filter(actor, subject_type)`

**Provider**: access-control
**Consumers**: prompt-registry
**Transport**: in-process
**Auth**: none
**Version**: in-repo

**Request carries**: the actor, and a subject type (`"prompt"` today).

**Returns**: `{mode: all | none | ids | namespaces, ids?, namespaces?}` — a **set**, pushed into the
consumer's own `WHERE` clause. Not a predicate, not a callback, not a row filter.

**`namespaces` added 2026-08-18** ([[ADR-0061]]), and it **answers** [[A-118]]'s own revisit condition
rather than postponing it. That condition reads *"a workspace's prompt count makes an explicit id list
too large to push into a query"*, watched by the `visible_filter_ids_size` histogram. Under namespace
grants a person with four folders holding two thousand prompts is four strings on the wire, and the
caller's query gains one disjunct it can evaluate itself:

```sql
WHERE workspace_id = :ws
  AND (owner_id = :actor OR id = ANY(:ids) OR namespace = ANY(:namespaces))
```

The histogram stays flat for the exact case that was going to move it.

**`mode` is a LABEL, not a discriminated union — corrected 2026-08-19, at build.** The four values were
first written up as mutually exclusive, and they cannot be: an actor can hold three per-prompt grants
**and** two folder grants at the same time, and a return shape that had to pick one of `ids` or
`namespaces` could not have expressed that person's visibility at all. The shipped
`VisibleFilter` therefore carries **both** payloads, and `mode` names whichever one is populated so the
`visible_filter_ids_size` histogram and the log line stay legible.

The consumer contract is unchanged and, importantly, **unbranched**:

> `mode == all` -> no filter. **Anything else** -> OR together every predicate you can evaluate
> yourself with both `ids` and `namespaces`.

There is exactly one `if` in a correct consumer, and it is the `all` short-circuit. That shape was
chosen for its failure direction: a consumer written before `namespaces` existed, which reads only
`ids`, **narrows** rather than widens — it shows too few prompts, which somebody reports, instead of
too many, which nobody does.

**Why the set form is the interface and not an optimisation** ([[A-118]]): without it, *"permission
filtering lives in the repository layer"* cannot be satisfied without a cross-module join the registry
forbids itself, and the version that ships under deadline pressure is the query with **no filter at
all**. The shape exists to make the correct implementation the easy one.

**Failure semantics**: raises. A list endpoint returning 5xx is correct here; a list endpoint returning
everything is not.

**`mode: none` is a real answer** and must render as an empty list, never as an error and never as an
unfiltered query. `mode: all` means the actor may see every subject of that type in the workspace — it
is not a bypass of tenancy, which RLS enforces underneath regardless (ADR-0045).

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-003 — `authenticate_api_key(secret)`

**Provider**: access-control
**Consumers**: gateway
**Transport**: in-process
**Auth**: none — this *is* the authentication
**Version**: in-repo

**Request carries**: the raw `prope_<key_id>_<secret>` string from the gateway's `Authorization` header.

**Returns**: `{workspace_id, key_id, scope}` or `null`. Never the stored hash, never the key row.

**Mechanism**: indexed lookup on `key_id`, then `hmac.compare_digest` against the stored hash. Keys are
**hashed, never encrypted** — the contrast ADR-0021 draws with a provider credential is the direction
of use: a consumer key is only ever *verified*, a provider credential must be *presented*. Deliberately
not argon2: this is on the hot path and the secret is high-entropy machine-generated, not a password.

**Failure semantics**: a `null` return is an authentication failure and the gateway answers in the
OpenAI error shape. A **raise** is a 5xx and the gateway does **not** fall back, does not serve a cached
principal, and does not admit the request — an unavailable oracle is not an allow. `/readyz` on the
gateway is gated on access-control being reachable for exactly this reason (INT-030).

**Not cacheable** ([[A-114]]). Together with INT-004 this carries a budget of **p95 < 5 ms** inside the
gateway's 50 ms, measured in the gateway's own load test rather than in isolation.

**Idempotency**: pure read. Updates `last_used_at` as a side effect, which is not part of the contract
and must never be on the request's critical path.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-004 — `may_resolve(key_id, model_name, namespace)`

**Provider**: access-control
**Consumers**: gateway
**Transport**: in-process
**Auth**: none
**Version**: in-repo

**Request carries**: the `key_id` returned by INT-003, the model name from the request's `model`
field — the bare name, with any `@<n>` / `@<version_id>` pin already stripped by the gateway — and, as
of 2026-08-18 ([[ADR-0061]]), the **namespace**. The third argument costs nothing: `ModelName.parse`
already splits `namespace/name` at the edge of every request, so it is a value the gateway holds.

**Returns**: `bool`. **Default-deny; empty scopes resolve nothing.**

**Two scopes, one `OR`, still one indexed read** ([[A-158]]). A key resolves a name in
`scope_model_names` **or** a namespace in `scope_namespaces`. Both arrays default `'{}'`, so
default-deny is unchanged and by the same mechanism — `= ANY('{}')` is false for every input, with no
branch anybody can forget. One namespace entry replaces the thousand name entries a product that owns a
folder used to need, which is the friction A-081 flagged as *"a cost worth watching in the pilot"*.

**Failure semantics**: raises -> 5xx, never an admit. Not cacheable.

**The refusal shape is a security requirement, not a courtesy** ([[A-081]], [[A-116]]): a scope refusal
must return **the same not-found response as an unknown model name**, so a leaked key cannot enumerate
the registry by observing which names refuse differently. The gateway owns rendering that, and the
boolean here carries no reason for it to leak.

**That property is unchanged within a namespace and deliberately weakened across namespaces**, as of
[[ADR-0062]]. An observe-enabled key forwards a call addressed to a namespace the workspace does not
use, so which namespaces exist is observable. Which prompt *names* exist is not — `finance/pricing` and
`finance/nothing` are both refused, byte-identically. The trade is priced in [[A-159]]: the disclosed
unit is coarse, the key's own scope already implies most of it, and each probe costs the attacker a
provider call in the victim's account that lands in three separate places.

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-005 — `authenticate_session(cookie)`

**Provider**: access-control
**Consumers**: the shared session dependency in `app`, used by every management route in
prompt-registry, evaluation, release-control, provider-access, call-ledger and access-control itself
**Transport**: in-process
**Auth**: none — this *is* the authentication
**Version**: in-repo

**Request carries**: the session cookie value.

**Returns**: `{user_id, workspace_id}` or `null`.

**A live row read, not a token verification.** Sessions are server-side rows and **self-contained JWTs
are forbidden** ([[A-108]], ADR-0022, ADR-0029). Sign-out deletes the row and is effective immediately;
a signed token would make that a lie for the rest of its lifetime. ADR-0052 does not change this — the
SPA is same-origin, so the `HttpOnly` `Secure` `SameSite=Lax` cookie survives unchanged, with **no JWT,
no CORS configuration and no CSRF token**.

**Failure semantics**: `null` -> 401 in the [[A-045]] envelope, and the SPA routes to sign-in. A raise
is a 5xx; no route may proceed with an unauthenticated actor on a caught exception.

**Idempotency**: pure read. Touching `last_seen_at` is a side effect outside the contract.

**Consumer note**: this is the one seam whose consumer is a shared dependency rather than a module — see
**Unmatched pairs** below.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-006 — `append(event)`

**Provider**: property-history
**Consumers**: prompt-registry (5 events), release-control (8), evaluation (4), provider-access (4),
access-control (10) — **31 registered actions across 5 writers**
**Transport**: in-process, **on the caller's connection inside the caller's open transaction** (ADR-0023)
**Auth**: none — property-history checks no permission and has no way to (A-044)
**Version**: in-repo

**Envelope carries**: `workspace_id`, `actor_type`, `actor_id`, `action`, `target_type`, `target_id`,
`scope_prompt_id`, `reason`, `details`, `occurred_at`. `seq` is database-assigned.

**The transaction is the contract, not an implementation detail.** This is the only reason *"no state
change without a trail, and no trail without a state change"* is a guarantee rather than a habit. An
HTTP call or a queue in this position would silently weaken it, which is why property-history is a
library on the caller's SQLAlchemy session and **not FastAPI, not a service, and mounts no route**.

**Failure semantics**: **raises, and the raise is the mechanism.** An unregistered action or an
unregistered `details` key aborts the caller's transaction, so the state change and its record are
atomic by construction. A caller that catches this has broken the product's central claim against a
spreadsheet. There is no "log the failure and continue" path and no dead-letter.

**Validation performed here, so no caller restates it**:
- The action must be in the 30-name closed vocabulary (ADR-0024). Two naming schemes were reconciled to
  `<target_type>_<past participle>` in [[A-120]].
- `details` keys are **allow-listed per action** ([[A-124]]). This is what stops a prompt body, a
  fallback answer, a credential, an eval output or a `prope.variables` value reaching the audit log
  through an undeclared field ([[A-046]]).
- `requires_reason` is enforced here for the three actions that carry one —
  `revision_break_glass_released`, `release_withdrawn`, `revision_changes_requested` — rather than by
  three separate promises in three lock files.

**`scope_prompt_id` is stamped at append**, which is what makes INT-024's Activity endpoint one indexed
read on `(workspace_id, scope_prompt_id, seq DESC)` instead of a join across four modules' tables
([[A-119]]).

**Ordering**: by `seq`, never by `occurred_at` — approve-and-release writes two events with the same
timestamp in one transaction ([[A-125]], [[A-076]]).

**Idempotency**: **none, and none is wanted.** Two identical appends are two facts. Retry is the
caller's transaction retrying as a whole.

**Spec**: generated from provider code + the seeded action registry -> in-repo type stubs.

---

## INT-007 — `read(scope, cursor, limit)`

**Provider**: property-history
**Consumers**: prompt-registry (a property's Activity), release-control (the decision trail),
provider-access (a configuration's activity)
**Transport**: in-process
**Auth**: **none, and this is the cycle break** — the caller has already answered *may you see this
subject* via INT-001 before asking what happened to it (A-044)
**Version**: in-repo

**Request carries**: `scope`, one of `{workspace_id, scope_prompt_id}` / `{workspace_id, target_type,
target_id}` / `{workspace_id, actor_id}`; plus cursor and limit per [[A-045]].

**Returns**: events ordered by `seq` **descending**, cursor-paginated.

**Failure semantics**: raises -> 5xx at the caller's edge. There is no degraded mode: a history screen
that renders partially is worse than one that errors, because it reads as a complete record.

**The load-bearing negative**: this function performs no permission check and **has no way to**. That is
what A-044 traded away to break the access-control cycle, and it is why property-history depends on
nothing. A caller that reaches this without having checked has leaked another workspace's decision trail
— RLS is the backstop (ADR-0045), not the control.

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-008 — `registered_actions()`

**Provider**: property-history
**Consumers**: the route-table test in CI; the five writing modules' own validation
**Transport**: in-process
**Auth**: none
**Version**: in-repo

**Returns**: `[{action, target_type, detail_keys, requires_reason}]` — the vocabulary as data.

**Why it is an interface and not a constant**: it lets a test assert that **every state-changing
endpoint names a registered action**, and it makes [[A-120]]'s rename checkable rather than trusted. A
30-value enumeration maintained in five lock files and one migration is exactly the kind of thing that
drifts silently; this is the seam that makes the drift a red build.

**Failure semantics**: raises. In CI that is a failed build, which is the point.

**Idempotency**: pure read.

**Spec**: generated from the seeded `history.history_action_registry` table -> in-repo type stubs.

---

## INT-009 — `resolve(model_name, pin)`

**Provider**: prompt-registry
**Consumers**: gateway
**Transport**: in-process
**Auth**: none — the gateway has already authenticated (INT-003) and scoped (INT-004)
**Version**: in-repo

**Request carries**: the bare model name, and an optional pin — `@<n>` (revision number) or
`@<version_id>`.

**Returns**: a `RevisionBinding` — body, provider config id, upstream model, generation parameters,
fallback answer, version id, revision number. Or a **miss**.

**The miss must distinguish two cases** ([[A-069]], ADR-0009): *model name unknown* and *model name
known, nothing released*. They are the same 404 to the caller and two different lines in
`prope_registry_resolve_miss_total`, which is the only way a withdrawal is visible as a withdrawal
rather than as a typo.

**A pin whose revision is not `Approved` is refused** — BR-03 is enforced by a **database constraint**,
not by application code, and this seam reads a pointer the constraint has already guaranteed. The
gateway never consults an approval record (ADR-0001).

**Failure semantics**: raises -> the gateway returns an OpenAI-shaped 500 and **does not** serve the
fallback answer. The fallback exists for an *upstream provider* failure ([[A-033]]), not for a Prope
failure — serving stored text when Prope itself is broken would hide the outage from the one metric that
would show it. `/readyz` is gated on prompt-registry being reachable (INT-030).

**Cached by the caller** for **30 s TTL, expiry only** (ADR-0012, [[A-080]]). An expired entry is never
served; there is no stale-if-error window; **nothing invalidates it** — not a release, not a restore,
not a withdrawal. Fan-out invalidation over the broker was reconsidered on merit after ADR-0028 removed
the no-broker premise, and rejected again. The cost is stated plainly: a withdrawal is effective
**within 30 seconds**, not immediately.

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-010 — `list_released(workspace_id)`

**Provider**: prompt-registry
**Consumers**: gateway
**Transport**: in-process
**Auth**: none — scoped by INT-004 at the gateway's edge
**Version**: in-repo

**Returns**: `[{model_name, version_id, revision_number}]` for prompts with a **current release**.

**Deliberately not the same query as `GET /api/v1/prompts`** — no cursor, no filters, released only, and
the actor is a consumer key rather than a person. Reusing the management list here would leak
unreleased and unpermitted prompts into `GET /v1/models` through a default argument nobody reviewed.

**Failure semantics**: raises -> OpenAI-shaped 500. The gateway filters the result through INT-004
before rendering, so this seam returns the workspace's releases and the *key's* scope is applied
afterwards.

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-011 — Registry read interface

**Provider**: prompt-registry
**Consumers**: evaluation (`get_revision`, `get_released_revision`), release-control (`get_revision`,
`get_diff`, `get_released_revision`)
**Transport**: in-process
**Auth**: none — both callers check INT-001 at their own edge first
**Version**: in-repo

**Returns**:
- `get_revision(version_id)` — body, provider config, upstream model, generation parameters, fallback
  answer, author, timestamp, change summary, status.
- `get_released_revision(prompt_id)` — the same shape for whatever is released now, or none.
- `get_diff(from_version_id, to_version_id)` — line-level diff of the body plus a **field-level**
  comparison of provider, model, parameters and fallback answer ([[A-015]], [[A-047]]).

**`get_diff` is computed server-side with stdlib `difflib` and `SequenceMatcher(autojunk=False)`.**
`autojunk` silently discards lines appearing in over 1% of a sequence longer than 200 elements, which on
a 32 KiB body with repeated short lines produces a diff that looks *wrong* rather than slow. It stays in
`app` after ADR-0052 — only the **painting** of the diff moved to the browser.

**Read-only. Neither consumer ever writes**, and evaluation's non-goals name the released pointer, the
approval record and the revision body as all belonging elsewhere.

**Failure semantics**: raises. For release-control this is the review screen failing to render, which is
correct — a decision surface that renders without its evidence is the failure [[A-074]] exists to
prevent. Evaluation treats it as a run error, never a case failure.

**Idempotency**: pure reads.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-012 — `set_revision_status(version_id, status, decision_id)`

**Provider**: prompt-registry
**Consumers**: release-control
**Transport**: in-process command
**Auth**: none — release-control has checked `revision.submit` / `revision.approve` via INT-001
**Version**: in-repo

**Request carries**: the version id, the target status (`Draft` | `In review` | `Approved`), and the
`decision_id` of the release-control record that justifies it.

**Returns**: void, or raises.

**Why this exists as a command rather than a write**: prompt-registry's lock originally had
release-control write `revision.status` directly, which put a **second writer** on the value BR-03's
released-pointer constraint reads. This seam is what makes ADR-0008's *"writes no table it does not
own"* true for the transition. **The provider validates the transition**, so the legal state machine
lives in one module.

**Failure semantics**: raises on an illegal transition, on an unknown version, or on a `decision_id`
that does not exist — and the raise aborts release-control's transaction, which also aborts its INT-006
append. A decision that could not move the status leaves no record claiming it did.

**Idempotency**: **not idempotent.** Re-issuing a transition that has already happened raises rather
than silently succeeding, so a double-submit is visible instead of absorbed.

**Enforcement of the seam itself is now a CI layering contract** (`import-linter`, ADR-0008 as amended),
plus the hourly reconciliation query as the runtime detector for the raw-SQL path the contract cannot
see. It is no longer a process seam — that degradation is recorded rather than assumed.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-013 — `set_released_revision(prompt_id, version_id, release_id)`

**Provider**: prompt-registry
**Consumers**: release-control
**Transport**: in-process command
**Auth**: none — release-control has checked `release.create` or `release.break_glass` via INT-001
**Version**: in-repo

**Request carries**: prompt id, target version id, the `release_id` of the release record, and
`expected_current_version_id` for the **compare-and-set** ([[A-072]]).

**Returns**: void, or raises.

**The only write to the released pointer in the entire system** ([[A-041]], ADR-0001). No other module
may issue it, and prompt-registry refuses to set it on its own behalf.

**Rejected unless the target revision's status is `Approved`** — and that refusal is a **database
constraint**, not an `if` in this function. BR-03 is non-negotiable in `00_context.md#constraints`, and a
constraint survives a code path nobody reviewed.

**Failure semantics**:
- Target not `Approved` -> raises; the constraint is the thing that raises.
- `expected_current_version_id` does not match -> raises a **conflict**, surfaced as 409 at
  release-control's edge. Someone released something else while this reviewer had the screen open, and
  overwriting it silently is how a release nobody decided reaches production.
- Any raise aborts release-control's transaction, and with it the release row and the
  `revision_released` append. **There is no release without a trail**, by transaction rather than by
  convention.

**Idempotency**: not idempotent by design — the compare-and-set is what makes a retry safe *or* loud,
and never quiet.

**Downstream timing, stated because it is a product-visible number**: the gateway's resolution cache is
**not** invalidated by this call (INT-009). A release is live for new resolutions **within 30 seconds**.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-014 — `clear_released_revision(prompt_id, release_id)`

**Provider**: prompt-registry
**Consumers**: release-control
**Transport**: in-process command
**Auth**: none — release-control has checked `release.withdraw`, its own distinct permission
**Version**: in-repo

**Request carries**: prompt id and the `release_id` of the withdrawal record.

**Returns**: void, or raises.

**A separate command rather than `set_released_revision(..., NULL)`**, and the reason is structural
([[A-069]], ADR-0009): a NULL argument would require the Approved-only constraint to grow a NULL
carve-out, and a carve-out in the constraint that enforces BR-03 is a hole in a non-negotiable rule to
save one function signature.

**Failure semantics**: raises if nothing is released — a withdrawal of nothing is a bug in the caller,
not a no-op. Aborts release-control's transaction along with its mandatory-reason `release_withdrawn`
append.

**Unblocks retire** ([[A-052]]): `POST /api/v1/prompts/{id}/retire` is refused while a release is
active, and this is the only way to clear that.

**The cost is documented at INT-009 and repeated here because this is where it is felt**: after a
withdrawal the gateway may keep serving the withdrawn revision for **up to 30 seconds**. ADR-0009's
"loudly" was amended to say so. Consumers see a `404`-shaped miss afterwards, counted separately from an
unknown name.

**Idempotency**: not idempotent.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-015 — `dispatch(...)`

**Provider**: provider-access
**Consumers**: gateway (`priority=interactive`, `stream` either way), evaluation (`priority=batch`,
`stream=false`)
**Transport**: in-process — in `app` for the gateway, in `worker` for evaluation's executor. **Same
function, two processes** (A-142 §1)
**Auth**: none inbound. **Deliberately not re-checked against access-control** — authorisation happened
at the calling module's edge, and a second check on the hot path is a second thing that can disagree
with the first
**Version**: in-repo

**Request carries**: `provider_config_id`, `upstream_model`, generation `parameters`, composed
`messages`, `stream`, `deadline_ms`, `priority`. **The credential never crosses this seam in either
direction** — the caller passes an id, provider-access decrypts in its own process ([[A-025]],
ADR-0014).

**Returns**: `DispatchResult` — an OpenAI-shaped response (or stream) plus a **usage object**, unknown
provider fields passed through untouched (ADR-0015). Usage reporting is always requested from the
provider ([[A-089]]).

**Or `DispatchError`** — a typed value, **not an exception**, carrying `class`, `origin`, and
`retryable` and `fallback_eligible` as **separate facts** ([[A-095]], ADR-0017). Error classes:
`timeout`, `rate_limited`, `credential_rejected`, `upstream_5xx`, `bad_request`, `content_filtered`,
`transport`.

**Exactly one attempt. This seam never retries** ([[A-088]]) — which is how the gateway's *never retry*
([[A-084]]) and evaluation's *retry transport errors only* ([[A-053]]) are both true without either
policy living here.

**Failure semantics by consumer**:

| | gateway | evaluation |
|---|---|---|
| `DispatchError` before first byte | serves the revision's **fallback answer**, marked in header, body and call record | run **error**, never a case failure ([[A-057]]) |
| `DispatchError` after first byte | stream ends; no fallback is possible and none is faked | same |
| `retryable` | ignored — the gateway never calls again | evaluation's own loop decides, up to A-053's policy |
| a genuine raise (a bug) | 500, no fallback | run error |

**Admission**: batch yields to interactive on the shared credential ([[A-093]], ADR-0016), bounded at
`batch_concurrency = 8` per provider config (ADR-0046). **A run can be slowed — never failed — by
production load.** The semaphore is per process, so it exists in both `app` and `worker`.

**Never refused for cost.** Ceilings refuse eval runs at INT-020, before the first dispatch; no dispatch
is ever refused here for spend ([[A-029]]).

**Idempotency**: **not idempotent — every call costs money.** Callers must not retry a dispatch whose
outcome is unknown; that is what `deadline_ms` and the `transport`-only retry rule exist to bound.

**Spec**: generated from provider code -> in-repo type stubs. The OpenAI response shape is
ADR-0015's internal contract and is asserted by tests today.

---

## INT-016 — `get_model_catalogue(provider_config_id)`

**Provider**: provider-access
**Consumers**: prompt-registry
**Transport**: in-process
**Auth**: none — prompt-registry checks `catalogue.read` via INT-001 first
**Version**: in-repo

**Returns**: `[{model_id, display_name, supports_streaming, available}]`. **No prices ever appear here**
— call-ledger owns money ([[A-030]], [[A-056]]).

**Two uses, one shape**: validating that a configuration exists and exposes the model a revision binds,
and populating the revision editor's model picker.

**Failure semantics — the one soft seam** ([[A-091]]). An unavailable or stale catalogue **degrades the
picker to free text; it never refuses a save.** The catalogue is discovered from the provider's own
list and is allowed manual entries precisely because provider endpoints omit models; treating it as
authoritative would block a legitimate revision on a third party's incomplete API.

**Idempotency**: pure read.

**Note the forbidden direction**: `DELETE /api/v1/providers/{id}` is refused while a revision binds the
configuration, and that refusal comes from the **foreign key** `revision.provider_config_id`, *not* from
provider-access asking prompt-registry. That edge does not exist. The response says **how many**
revisions bind it and links to the registry's filter rather than naming them.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-017 — `get_review_summary(prompt_id, version_id)`

**Provider**: evaluation
**Consumers**: release-control
**Transport**: in-process read
**Auth**: none — release-control has checked `revision.approve` via INT-001
**Version**: in-repo

**Returns** a `ReviewSummary`: a **per-suite list** — suite name, pass / fail / error counts, the
baseline run it was compared against and when, that suite's cost delta — plus a **rollup** carrying the
total delta, the cost-warning flag, and **`requires_acknowledgement`**.

**`requires_acknowledgement` is computed here and never restated by the consumer** ([[A-058]],
ADR-0005). It is true when **any** suite has a failing case, so the two carve-outs are applied once, in
one place: an **error is not a fail** ([[A-057]]) and an **empty suite is not a pass** ([[A-059]]).
Release-control **enforces** it and does not recompute it — that split is the whole of A-042.

**The rollup's total cost delta is withheld whenever any suite withheld its own**, and the valid
per-suite deltas are still returned ([[A-062]]). A total computed over a partly unpriced or errored run
is not a total.

**Pull-based, one direction. Evaluation never calls release-control** — there is no notification, no
callback and no broker message when a run finishes. A finished run is discovered by this pull when the
review screen renders ([[A-042]]) and by the client's poll of INT-025.

**Failure semantics**: raises. **Release-control's response to a summary it could not pull is not to
proceed silently** — the acknowledgement reason becomes **mandatory** when the summary could not be
pulled, exactly as when it reported failures ([[A-070]]). An approval recorded with no evidence and no
statement of why is the failure this whole module exists to prevent.

**Never cached.** The review screen is composed at read time, every time ([[A-047]]).

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-018 — `prope.call_record`

**Publisher**: gateway, via call-ledger's `enqueue(call_record)` — call-ledger owns the publish, the
confirm and the fallback; **the gateway itself declares and publishes nothing**
**Subscribers**: call-ledger's drain, running in `worker`
**Transport**: RabbitMQ 4.x, durable queue, persistent messages, **publisher confirms** (ADR-0028)
**Auth**: broker credentials from the single `.env` on the VM (ADR-0032)
**Delivery**: **at-least-once**
**Partition key**: none — RabbitMQ has no partitions. The drain **groups each consumed batch by
`workspace_id`** and opens one `SET LOCAL app.workspace_id` transaction per group (ADR-0040)
**Retention**: the queue's, not a policy — messages live until acked. Stored bodies are a separate
question ([[A-040]], 30-day placeholder, OQ-013)
**Evolution**: **additive only**; `schema_version` starts at 1 (A-142 §5)
**DLQ**: `prope.call_record.dlq`
**Version**: envelope `schema_version: 1`

**Envelope carries** (A-142 §5): `schema_version`, `call_id`, `workspace_id`, `occurred_at`, `producer`.
**Payload carries**: version id, model name, consumer key id, `source` (`gateway` | `eval`), outcome,
timings, usage, and the request and response bodies.

**`call_id` is generated by the CALLER at request time** ([[A-099]]) and is the idempotency key. The
drain **upserts** on it.

**The write path is broker-first with a direct-write fallback** (ADR-0041):

1. Publish, after the response is flushed ([[A-087]]) — never before, because
   `00_context.md#constraints` forbids persistence on the response path non-negotiably.
2. On a **failed or nacked confirm**, write the metadata row **directly to PostgreSQL inline** and count
   it. **Bodies are dropped in that path**, as [[A-037]] already allows: metadata is the accountability
   claim, bodies are best-effort by declaration.
3. **There is no spill file.** ADR-0041 deleted it, along with its replay job, its readiness clause, its
   disk-full failure mode and three metrics.

**Failure semantics**:

| Failure | Behaviour |
|---|---|
| Broker unreachable / nacked confirm | inline direct write, `fallback_direct_write_total` and `publish_failed_total` increment. **Not un-ready** — withholding readiness would take the gateway out of service to protect a path that is working |
| Broker **and** database unavailable | `metadata_dropped_total` increments. **Stays 0 and stays a page** — it now means a genuine incident rather than an ordinary deploy |
| Redelivery of an already-written record | upsert on `call_id` changes nothing. **This is why a redelivery cannot move a workspace's spend** |
| Late delivery of a record the fallback already wrote | same upsert, same outcome. ADR-0041 creates both duplicate shapes and A-099 absorbs both |
| Poisoned message | dead-letters to `prope.call_record.dlq` after the configured attempts. A DLQ depth above zero is an alert, never a silent discard |
| **Process hard-killed between flush and publish** | **the record is lost and nothing counts it** — recorded honestly as [[A-139]]. Window is the enqueue span, p95 < 1 ms; a graceful stop drains and does not hit it |

**`enqueue()` never raises into the caller, ever**, and never applies backpressure. It runs after the
response is flushed, where a raise is a crashed request task at worst and a log line at best.

**This is the only queue in Prope.** ADR-0028 was argued over three asynchronous workloads; evaluation
subsequently chose a table claim (ADR-0049) and release-control's sweep is a timer (ADR-0051). Worth
knowing before someone adds the second — and worth knowing *why*: redelivery is a **feature** here
because the drain is idempotent on `call_id`, and a **bill** in evaluation because a redelivered run
re-dispatches paid cases against a workspace's own key.

**Schema**: generated from call-ledger's pydantic model at build time -> in-repo, published as the
producer's contract.

---

## INT-019 — `price_usage(run_id, usage_rows)`

**Provider**: call-ledger
**Consumers**: evaluation
**Transport**: **in-process, not the broker.** Both sides run in `worker` — evaluation's executor and
call-ledger's writer are the same process
**Auth**: none
**Version**: in-repo

**Request carries**: `run_id`, and one usage row per eval case with a **caller-generated `call_id`**
([[A-099]]), `version_id`, `source=eval`, and **no body** ([[A-055]]). Eval outputs live on
`case_result`, never in `call_body`.

**Returns**: void.

**Priced at write time** against the price row **in force at the call's own timestamp**, and the cost is
stored **with the price row that produced it** ([[A-030]], ADR-0019). A price is never re-derived, which
is why the price table has no cache: a stale price row would be a permanently wrong number with no
correction path.

**Never estimated.** A call with no usage records **unknown tokens**; a call with no price row records
**unpriced cost**. Never zero, never inferred from prompt length — `00_context.md#constraints` makes
*"cost must be measured from actual runs"* non-negotiable (BR-07, [[A-101]]).

**Eval usage lands in the same `call_record` table as gateway traffic under `source=eval`**, so one
spend total covers both ([[A-098]]) — which matters because gateway traffic is usually what pushes a
workspace toward the ceiling that then refuses a run.

**Failure semantics**: raises -> evaluation records a **run error**, not a case failure. A run whose
usage could not be priced must not report a cost delta, and INT-021's counts are how the review screen
says so.

**Idempotency**: **idempotent on `call_id`** — the same upsert INT-018's drain uses.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-020 — `check_spend_ceiling(workspace_id)`

**Provider**: call-ledger
**Consumers**: evaluation, **before a run's first dispatch**
**Transport**: in-process
**Auth**: none
**Version**: in-repo

**Returns**: `{allowed: bool, reason?}`. **Never a figure** ([[A-056]]) — the ceiling is a boolean
surface, and there is no billing dashboard in the MVP.

**Ceilings refuse eval runs and never gateway traffic** ([[A-029]]). Both the monthly and the per-run
ceiling default **off**.

**Failure semantics — this is the one seam that FAILS OPEN** ([[A-104]]). If the check cannot be
evaluated it returns `allowed: true` and increments a counter. It guards an optional, off-by-default
feature, and blocking a reviewer's evidence over a billing lookup is the worse trade. The counter is the
control: an open-failing check that nobody watches is an off switch.

**Checked once, before the first dispatch of a run** — never per case, and never by call-ledger during a
call. A run that starts under the ceiling and crosses it mid-run finishes.

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-021 — `get_run_totals(run_id)`

**Provider**: call-ledger
**Consumers**: evaluation
**Transport**: in-process
**Auth**: none
**Version**: in-repo

**Returns**: `{input_tokens, output_tokens, cost, currency, unpriced_count, unknown_usage_count}`.

**The two counts are part of the answer, not diagnostics.** A delta computed over a partly unpriced run
is not a delta, and the review screen has to be able to say which ([[A-101]], ADR-0019). Evaluation
subtracts two of these — candidate and baseline — to produce the cost delta, and withholds the delta
whenever either side is incomplete, propagating that through INT-017's rollup.

**`currency` travels with the figure and is displayed in it. There is no FX conversion** ([[A-107]]) —
an exchange rate would be a second effective-dated table. Two runs priced in different currencies
produce **no delta**, not a converted one.

**Failure semantics**: raises -> run error at evaluation, and no delta.

**Idempotency**: pure read.

**Spec**: generated from provider code -> in-repo type stubs.

---

## INT-022 — Gateway: `POST /v1/chat/completions`, `GET /v1/models`

**Provider**: gateway (a **separate ASGI application object**, ADR-0050)
**Consumers**: consuming products' OpenAI client SDKs — outside this repository and outside this team
**Transport**: HTTPS through Caddy, which routes `/v1/*` **by path prefix in configuration**
**Auth**: consumer API key in `Authorization`. Hashed at rest, verified in constant time (ADR-0021)
**Rate limit**: **20 concurrent in-flight requests per `key_id`** ([[A-143]])
**Version**: `/v1` — **OpenAI's wire version, not ours to bump**

**Request carries**: an OpenAI chat-completions request whose `model` field is a Prope **model name**
(`namespace/name`), optionally pinned as `name@<n>` or `name@<version_id>`, plus an optional top-level
`prope` object carrying `variables` ([[A-078]]).

**Returns**: the OpenAI chat-completions response or stream, with **the identity of what served it in
both headers and body** — version id, model name, revision number, `pinned`, `fallback` ([[A-079]]).
`GET /v1/models` returns the OpenAI list shape, `id` being the model name, containing only prompts with
a current release that this key may resolve.

**Errors are OpenAI-shaped, never the [[A-045]] management envelope** — the gateway is explicitly exempt
([[A-026]]). Unimplemented OpenAI routes return **501 in the OpenAI error shape**.

**The routing separation is structural, not an ordering rule.** Caddy dispatches `/v1/*` in
configuration, so no FastAPI catch-all can shadow `management.mount("/v1", gateway)` and hand
`index.html` to a consumer's SDK. Serving the SPA from FastAPI would have made wire compatibility depend
on route-registration order with no failure signal — rejected on the grounds ADR-0050 established.

**Failure semantics**:

| Condition | Response |
|---|---|
| Bad or unknown key | OpenAI-shaped 401 |
| Key valid, model out of scope | **the same not-found as an unknown model name** — a leaked key cannot enumerate the registry ([[A-081]], [[A-116]]) |
| Model name unknown, or known with nothing released | OpenAI-shaped 404. Counted separately (INT-009) |
| Pin targets a non-`Approved` revision | refused. BR-03, enforced by a database constraint |
| Caller supplies a system message | **refused** — not merged, not silently dropped (ADR-0011) |
| At the concurrency cap | OpenAI-shaped **429** + `Retry-After`. Never queued, never delayed ([[A-143]]) |
| Upstream fails **before the first byte** | the revision's **fallback answer**, marked in header, body and call record ([[A-033]], [[A-034]], ADR-0013) |
| Upstream fails **after the first byte** | the stream ends. **No fallback**, and none is faked |
| Prope's own dependency fails (registry, access-control) | 500. **No fallback** — the fallback is for provider failure, not for Prope failure |
| call-ledger unavailable | **nothing.** Logging is off the response path; the call is served normally |

**The gateway never retries and never rewrites a caller's request to make it succeed** ([[A-084]]).

**Idempotency**: **none — every call costs the workspace money.** Retry is the caller's decision and its
bill. Prope generates a `call_id` per received request; two retries are two calls, two records, two
charges, correctly.

**Timing consumers can rely on**: added latency **p95 < 50 ms**, of which INT-003 + INT-004 hold **< 5
ms**. A release or restore is live **within 30 seconds**, not immediately (INT-009).

**Spec**: OpenAI's published chat-completions schema is the contract; Prope's additions (`prope.variables`,
the identity headers) are generated from gateway code at build time -> in-repo.

---

## INT-023 — provider-access -> the workspace's upstream provider

**Provider**: the workspace's own upstream (external, not a module)
**Consumer**: provider-access — **the only module in Prope that makes one**
**Transport**: HTTPS, outbound. **Prope's only workspace-credential outbound internet egress** ([[A-043]]); app-owned Agent traffic is separately registered as INT-033.
**Auth**: the workspace's own credential, decrypted only in this process, held in a **60 s in-memory
cache that exists in two processes** and is never invalidated ([[A-092]], ADR-0014)
**Version**: the provider's

**Request carries**: an OpenAI-compatible chat-completions request, or a model-list request.

**Returns**: the provider's response, **normalised into the OpenAI chat-completions shape with unknown
fields passed through untouched** (ADR-0015), plus a usage object ([[A-089]]).

**The destination is validated, and this is a security requirement** (ADR-0047):
- `base_url` is checked against a **scheme allow-list**.
- It is **refused if it resolves to loopback, link-local, or private ranges** — **at save time and again
  at dispatch time**.
- **Dispatch connects to the address it validated**, with the hostname preserved for TLS SNI.
- **Redirects are disabled.** A 302 to `169.254.169.254` is the whole attack this closes.

**Failure semantics**: every failure is classified into one closed set of typed errors carrying
`fallback_eligible` and `retryable` as separate facts, and returned as a `DispatchError` at INT-015 —
never raised, never retried here. **A provider being down NEVER makes provider-access un-ready**: an
unreachable provider is the case the fallback answer exists for, and reporting it as unreadiness would
take the gateway down with it.

**A provider that ignores `include_usage` is an admission question here, not a gateway workaround**
(ADR-0013's closing obligation).

**Idempotency**: none — every call costs money. **Exactly one attempt** ([[A-088]]).

**Spec**: the provider's own; Prope pins only the normalised shape it returns inward (ADR-0015).

---

## INT-024 — Management API: prompt-registry

**Provider**: prompt-registry, in `app`
**Consumers**: the web SPA (`prope-web`) — same origin, served by Caddy from the same host
**Transport**: HTTPS -> Caddy -> `app:8000` on `/api/*`
**Auth**: session cookie via INT-005. **No JWT, no CORS, no CSRF token** (A-142 §8)
**Version**: `/api/v1`, frozen for the MVP
**Conventions**: [[A-045]] envelope, cursor pagination (`limit` 50 / max 200), ULID `prm_` and `rev_` ids

**Routes**: `GET|POST /api/v1/prompts` · `GET|PATCH /api/v1/prompts/{id}` ·
`POST /api/v1/prompts/{id}/retire` · `GET|POST /api/v1/prompts/{id}/revisions` ·
`GET /api/v1/revisions/{version_id}` · `GET /api/v1/prompts/{id}/diff?from=&to=` ·
`GET /api/v1/prompts/{id}/activity`

**Permission filtering is in the repository layer**, via INT-002 pushed into the `WHERE` clause — not
per row after the query. A subject the actor may not see is **not-found, never forbidden** ([[A-116]]).

**`/activity` returns every event scoped to the prompt** — revisions, submissions, approvals, releases,
restores, suite edits and grants — written by **four modules against six target types**, as **one
indexed read** on `(workspace_id, scope_prompt_id, seq DESC)` (INT-006, INT-007). Ordered by `seq`,
never by timestamp.

**`/retire` is refused while a release is active** ([[A-052]]); INT-014 is the only way to clear it.

**`search_text` is a second copy of the prompt body and must never appear in a response** — it exists
for the `pg_trgm` GIN index and nothing else.

**Failure semantics**: `404` for not-found and for not-permitted alike · `409` on a concurrent revision
conflict · `422` for validation with `details` · `5xx` for any raised in-process seam, with
`request_id` in the envelope. The SPA renders the envelope's `message`; it never parses `code` strings
into behaviour beyond auth.

**Idempotency**: none (A-142 §7). A duplicate revision is immutable, visible, and changes nothing about
what is released.

**Spec**: generated from FastAPI + pydantic v2 at build time -> OpenAPI at `/api/v1/openapi.json`.

---

## INT-032 — Prompt identity for conversion authorization

**Provider**: prompt-registry
**Consumer**: prompt-conversion
**Transport**: in-process repository read

Returns the prompt's identity, workspace, owner, and access level so conversion
can call INT-001 for `revision.create`. It returns no revision body and offers no
write. The dependency is one-way: prompt-registry does not import conversion.

---

## INT-033 — App-owned conversion Agent

**Provider**: OpenAI, configured only with `APP_OPENAI_*`
**Consumer**: prompt-conversion
**Transport**: HTTPS Chat Completions with a strict JSON schema

The source is explicitly submitted untrusted data. Prope validates structured
blocks and serializes XML itself. One invalid response may be repaired once; the
conversion breaker and metrics are independent from prompt-search.

---

## INT-034 — `record_observation(...)`

**Provider**: prompt-observation
**Consumer**: gateway — and no one else, ever
**Transport**: in-process (A-142 §1), in the caller's container
**Auth**: none — the gateway authenticated the consumer key at its own edge

Registered 2026-08-18 ([[ADR-0059]], [[ADR-0060]]).

**Carries**: the caller's message set, the upstream model name they asked for, the `call_id` the
gateway generated at request time, the `key_id`, and the arrival time. Nothing else — no resolution,
no revision, no permission decision, because none of those exist on the path this is reached from.

**Reached only on the forwarded path**, which is a request whose model name produced
`MissReason.UNKNOWN_MODEL` on a key carrying `observe_provider_config_id` ([[A-153]]). A served call
never reaches it and neither does any refusal.

**Two properties are contract-tested rather than assumed, and they are INT-018's two**: it is called
**after the response is flushed**, in the same background task that hands the call record to
call-ledger, and it **never raises**. The gateway's p95 rests on both, and a seam that raised would
turn a logging failure into a 500 on a request that had already succeeded.

**It does not publish to the broker.** ADR-0028 declares one queue; the write here is direct
([[A-155]]), because a lost observation costs a counter where a lost call record costs money. A
failure increments `observation_write_failed_total` and is abandoned.

**No read direction exists and none is permitted.** The gateway never queries this module — an edge
back would be the first step toward consulting the inventory during a call, which is the same rule
that keeps the gateway out of `call-ledger` in the read direction.

---

## INT-035 — Management API: prompt-observation

**Provider**: prompt-observation
**Consumers**: the web SPA
**Transport**: HTTPS through Caddy, `/api/v1` — [[A-045]]'s envelope, [[ADR-0053]]'s machine `code`
**Auth**: session cookie
**Version**: `/api/v1`, frozen

Registered 2026-08-18 ([[ADR-0060]]). **Seven routes**, and each checks `prompt.read` against a subject
carrying the observation's **namespace** before it reads anything ([[ADR-0061]]).

*Amended 2026-08-19, at build: six became seven.* [[SR-4]] requires *"a delete and a redact route from
the first commit"* and this table listed one route doing both jobs, described as *"removes the stored
bodies"*. They are different operations with different outcomes — redact keeps the group counting and
loses its text; delete removes the group — and one route could not have been both without a mode flag
nobody would read correctly under pressure.

*Amended 2026-08-18, same day.* This first read *"each checks `prompt.create` against the workspace"*,
because an observation had no container and the inbox borrowed the nearest action. ADR-0061 supplies
one: an observation carries a namespace, so the check is the ordinary one against the ordinary
attribute. The borrowing also had an inversion in it — `prompt.create` is what a Prompt Owner holds on
their first day, and it was being made to grant the widest read in the product.

| Route | What it does |
|---|---|
| `GET /api/v1/observations` | the discovery inbox — one row per fingerprint group, with counts and dates |
| `GET /api/v1/observations/{id}` | one group: current body, inferred variable slots, the bodies seen under it |
| `POST /api/v1/observations/{id}/proposal` | returns a canonical body with `{{placeholder}}` slots. **Writes nothing** |
| `POST /api/v1/observations/{id}/adopted` | records the `prompt_id` this group became. Idempotent |
| `POST /api/v1/observations/{id}/dismissed` | records a decision not to govern this one. Reversible |
| `POST /api/v1/observations/{id}/redacted` | removes the text, keeps the counts and the dates |
| `DELETE /api/v1/observations/{id}` | removes the group and its sightings outright |

**The proposal route is the shape of the whole module.** It returns a body for a person to post through
prompt-registry's own create routes; it does not create the prompt, and it does not create the revision.
That is prompt-conversion's rule — *conversion never saves a revision* — applied for the same reason:
an adoption must be an act somebody performed, so that non-negotiable #1 needs no new enforcement.

**Redact keeps counting.** A redacted group holds its `sighting_count`, its dates and its upstream
models and loses only `current_body` and every stored sighting body — so the inventory still says *there
was something here*, and the write path pins the redaction rather than restoring the text on the next
call from a product that is still sending it.

**`DELETE` and the redact route both exist before the retention policy does** ([[OQ-148]]), deliberately. This is the first table
in Prope holding customer text that arrived without an explicit submission, and the answer to *"take
that one out"* must not be a migration.

**BR-01 reaches an observation through its namespace.** This entry first said the opposite — that an
observation has no owner and no access level, so private-by-default had nothing to key on, and
visibility was workspace membership. That was a real widening with no fix available inside the module.
[[ADR-0061]] closes it by giving the thing a container instead of an owner: each consumer key names the
namespace its discovered prompts land in, and who may see one product's ungoverned prompts is one
`namespace_grant`. Two products' observations do not mix. What remains for [[OQ-147]] is the policy
question alone — may this data be held at all — which is now about one folder with one named grantee.

---

## INT-036 — `list_namespaces(workspace_id)`

**Provider**: prompt-registry
**Consumers**: gateway
**Transport**: in-process
**Auth**: none
**Version**: in-repo

Registered 2026-08-19, at build ([[ADR-0062]]). **Request carries** the workspace id. **Returns** a
`frozenset[str]`: every namespace the workspace uses, taken as the union of `registry.folder.slug` and
the distinct `registry.prompt_property.namespace`.

**It backs the entry rule and nothing else.** [[A-156]] forwards a call only when the model string is
*not addressed to a namespace this workspace uses*, and this is the set that decides. A name inside one
of these resolves or refuses exactly as it always did, for every key.

**Why it is here and not in access-control.** The obvious home looked like `may_resolve`, which already
takes the namespace as a parameter — and putting it there would have made access-control read
`registry.folder`, which [[ADR-0020]] and the module map both forbid. The edge that already exists runs
gateway -> prompt-registry, so the gateway asks here. `access_control/permissions.py` carries a comment
block recording the absence, so the next person to reach for the obvious home finds the argument rather
than repeating it.

**Cached by the CONSUMER on [[ADR-0012]]'s existing 30 s TTL**, in the gateway's own `NamespaceCache`
beside the resolution cache. Nothing invalidates it; it expires, for the reason the cache beside it
expires. A newly created namespace is therefore unrecognised for up to one TTL, during which a call to
it is forwarded and observed rather than refused — the same staleness ADR-0012 already accepts for the
released pointer, in the same direction, costing one observation somebody dismisses.

**Not permission-filtered, and it must not be.** It answers *is Prope holding anything under this name*
— a fact about the tenant, not about an actor — and the caller is a consumer key rather than a person.
[[A-159]] prices what that discloses: an observe-enabled key can learn which namespaces exist and still
nothing about which prompt names do, and each probe costs the attacker a provider call billed to the
victim's own account.

**Failure semantics**: raises, like every other read on this seam. **Idempotency**: pure read.

---

## INT-031 — Management API: prompt-conversion

**Provider**: prompt-conversion, in `app`
**Consumers**: the web SPA
**Transport / Auth / Version / Conventions**: as INT-024.

**Route**: `POST /api/v1/prompt-conversions` with `source_text`, normalized
`source_format`, and optional `prompt_id`. New-prompt conversion requires
`prompt.create`; existing-prompt conversion requires `revision.create`.

The source is untrusted data sent to the app-owned OpenAI service only after an
explicit user action. The Agent returns Pydantic-validated blocks, never XML.
Prope serializes and escapes those blocks, verifies every `{{variable}}`, and
returns an editable preview with `Cache-Control: no-store`. The route performs no
revision write. Invalid source is `422`, invalid Agent output after one repair is
`502`, and service timeout or open circuit is `503`.

---

## INT-025 — Management API: evaluation

**Provider**: evaluation, in `app`
**Consumers**: the web SPA
**Transport / Auth / Version / Conventions**: as INT-024. ULID `evr_` ids

**Routes**: `GET|POST /api/v1/prompts/{id}/eval-suites` · `GET /api/v1/eval-suites/{suite_id}` ·
`GET /api/v1/prompts/{id}/eval-suites/{name}/versions` · `PUT /api/v1/eval-suites/{suite_id}` ·
`POST /api/v1/prompts/{id}/eval-runs` · `GET /api/v1/eval-runs/{run_id}` ·
`GET /api/v1/eval-runs/{run_id}/cases` · `GET /api/v1/prompts/{id}/comparison?candidate={version_id}`

**`PUT /eval-suites/{id}` creates the next version and never mutates one** — a suite edit changes the
yardstick every later comparison is measured with, which is why an eval module writes to an audit log at
all.

**`POST /eval-runs` returns `202` and one run id per suite.** Submitting a revision runs **every** suite
the prompt currently has, one run each ([[A-062]]); a named subset is a re-run. **The client polls
`GET /eval-runs/{run_id}`** — there is no push, no websocket and no broker message, and a queued run is
**claimed** by `worker`'s 1 s poll of `eval_run` with `FOR UPDATE SKIP LOCKED` (ADR-0049), which is a
database read rather than a subscription.

**Refused when a configured spend ceiling is reached** (INT-020) — the only refusal a ceiling ever
produces anywhere in Prope.

**Failure semantics**: `202` then a terminal run status; an upstream failure is a **run error**, never a
case failure, and an error is **not a fail** for `requires_acknowledgement` ([[A-057]]). `409` when a
run is already in flight beyond `max_concurrent_runs = 2` per workspace.

**Eval case inputs and stored outputs carry the same sensitivity as prompt bodies** — never logged,
never a metric label, never in a history event ([[A-046]]). Retention inherits OQ-013.

**Idempotency**: none. A duplicate `POST /eval-runs` costs a new run, which is precisely why evaluation
declined the broker.

**Spec**: generated from FastAPI + pydantic v2 -> OpenAPI.

---

## INT-026 — Management API: release-control

**Provider**: release-control, in `app`
**Consumers**: the web SPA — **two actor roles on one surface**: Prompt Owner (submit, request restore,
request withdrawal) and Reviewer / Approver (review, approve, request changes, release, break-glass,
close a task)
**Transport / Auth / Version / Conventions**: as INT-024. ULID `rel_` ids

**Routes**: `POST /api/v1/prompts/{id}/revisions/{vid}/submit` ·
`GET .../review` · `POST .../approve` · `POST .../request-changes` ·
`POST .../approve-and-release` · `POST /api/v1/prompts/{id}/releases` ·
`POST /api/v1/prompts/{id}/releases/break-glass` · `POST /api/v1/prompts/{id}/releases/withdraw` ·
`GET /api/v1/prompts/{id}/releases` · `GET /api/v1/review-tasks` ·
`POST /api/v1/review-tasks/{task_id}/close`

**Five distinct permissions, not one**: submit, approve, release, break-glass, withdraw
(`00_context.md#constraints`, [[A-007]], [[A-069]]). A refusal **names the missing permission** when the
actor can see the subject, and is not-found when they cannot.

**`GET .../review` is composed at read time and never cached** ([[A-047]]) — the registry's diff
(INT-011), evaluation's per-suite summary (INT-017), and this module's own decision state.

**Human approval is mandatory and there is no auto-release of any kind.**
`POST .../approve-and-release` requires **both** permissions, refuses naming the missing one, and is one
request / two rows / one transaction / two history events ([[A-076]]) — *a convenience over the two
writes, never a third kind of decision*. A person deliberately performs it.

**Self-approval is recorded, never refused** — flagged `self_approved` ([[A-008]], ADR-0010). No
segregation-of-duties rule exists anywhere in Prope; eligibility is a permission question and nothing
else.

**Mandatory reasons, enforced at INT-006's append by `requires_reason`**: break-glass, withdrawal,
request-changes. Plus the acknowledgement reason when `requires_acknowledgement` is set — **and when the
summary could not be pulled at all** ([[A-070]]).

**`approval.evidence_digest` stores the evidence as it stood at the moment of decision** — run ids,
per-suite counts, cost delta, baseline timestamps ([[A-074]]) — and stores **counts, ids and money
only, never model outputs or case inputs**. The one module that pre-empted OQ-013.

**Break-glass creates a 24-hour follow-up review task** ([[A-009]], [[A-073]]). It **never closes itself
on a timer**; `POST /review-tasks/{id}/close` records a note. That follow-up is the entire mechanism
keeping break-glass exceptional, and `BreakGlassTaskOverdue` is what makes it visible.

**Failure semantics**: `409` on the compare-and-set (INT-013) — someone released something else while
this screen was open · `409` on submit when another revision of this prompt is already In review
([[A-067]]) · `422` naming the missing mandatory reason · `5xx` when INT-017 raises, **with the approve
path still available and its reason now mandatory**, never silently proceeding.

**Every write appends history in the same transaction** (INT-006). There is no release without a trail.

**`approval.comment`, `release.reason` and `acknowledgement_reason` are free-text human sentences** —
stored, rendered in the property history, and **never written to a log line or a metric label**
([[A-046]]), because they can name a customer or an incident.

**Idempotency**: none; the compare-and-set is the guard (A-142 §7).

**Spec**: generated from FastAPI + pydantic v2 -> OpenAPI.

---

## INT-027 — Management API: provider-access

**Provider**: provider-access, in `app`
**Consumers**: the web SPA — Workspace Admin
**Transport / Auth / Version / Conventions**: as INT-024. ULID `prv_` ids

**Routes**: `POST|GET /api/v1/providers` · `GET|PATCH|DELETE /api/v1/providers/{id}` ·
`POST /api/v1/providers/{id}/credential` · `POST /api/v1/providers/{id}/verify` ·
`GET /api/v1/providers/{id}/models` · `POST .../models/refresh` · `POST .../models`

**The credential is write-only across this entire seam, and that is non-negotiable.**
`00_context.md#constraints`: *"Provider credentials are supplied by the workspace, encrypted at rest,
never returned by a read API, and redacted in logs and audit records."*
- It is accepted in the body of `POST /providers` and `POST /providers/{id}/credential` and **never
  echoed back**.
- Reads return configuration, adapter, base URL, status, `last_verified_at`, `verification_status`, and
  the credential's **last four characters**. **There is no field, parameter, or flag that returns it.**
- Rotation **replaces the record**; there is no readable history ([[A-092]]).
- History events record **that** a rotation happened and by whom, **never what changed** ([[A-046]]).

**A credential is probed live before the record is saved active** ([[A-090]]), and re-probed on
rotation. `POST /verify` re-runs it on demand.

**Credential-bearing actions are their own permissions** — `provider.configure`,
`provider.rotate_credential`, `provider.disable`, `catalogue.read` — not sub-cases of workspace
administration and not implied by prompt-edit rights ([[A-007]], NFR-03).

**Failure semantics**: `422` when the live probe fails, **with the record not saved active** · `409` on
`DELETE` while revisions bind the configuration, **stating how many and linking to the registry's
filter** rather than naming them, because that direction is a forbidden edge (INT-016) · a
`base_url` that resolves to a private range is **refused at save time**, not merely at dispatch
(INT-023, ADR-0047).

**Idempotency**: none.

**Spec**: generated from FastAPI + pydantic v2 -> OpenAPI.

---

## INT-028 — Management API: call-ledger

**Provider**: call-ledger, in `app`
**Consumers**: the web SPA — Workspace Admin
**Transport / Auth / Version / Conventions**: as INT-024. ULID `cal_` ids, **generated by the caller**
at request time (A-099), not here

**Routes**: `POST|GET /api/v1/prices` · `GET /api/v1/prices/unpriced` ·
`PUT /api/v1/workspaces/{id}/spend-ceiling` · `PUT /api/v1/workspaces/{id}/retention`

**The price table is append-only and effective-dated.** Superseding a price is a **new row, never an
edit** ([[A-102]]); `GET /prices` returns superseded rows with their effective ranges. Each row carries
its **currency** explicitly, and there is no FX conversion ([[A-107]]).

**`GET /prices/unpriced`** returns the `(provider, upstream_model)` pairs that have produced calls with
no price row. It is the worklist behind `ProviderPriceMissing` and **the only spend-shaped screen in the
MVP** — there is no billing dashboard, and the ceiling answers a boolean.

**`PUT /retention`** sets the body retention window, default **30 days** ([[A-040]]). It is a setting
**from day one** so that OQ-013's answer is a configuration change rather than a migration.

**There is no body read path.** No viewer, no export, no endpoint ([[ADR-0018]], [[A-105]]). The store
is write-then-delete until OQ-013 sets a policy, and `ledger.call_body` is excluded from the nightly
dump (`--exclude-table-data`, ADR-0039) so a restore cannot silently double the retention window.

**This module exposes nothing that needs a permission check**, which is exactly why it can have no
dependency on access-control — its only edge would be the one that turns a ledger into a caller
(ADR-0018). Route-level session auth (INT-005) is the boundary; there is no INT-001 call here.

**Failure semantics**: `422` on a price row with an ambiguous effective range · `5xx` on database
failure. A ceiling that cannot be read **fails open** at INT-020, not here.

**Idempotency**: none on these routes; the write path's idempotency is `call_id` at INT-018 / INT-019.

**Spec**: generated from FastAPI + pydantic v2 -> OpenAPI.

---

## INT-029 — Management API: access-control

**Provider**: access-control, in `app`
**Consumers**: the web SPA — every signed-in person for `/auth`, Workspace Admin for the rest
**Transport / Auth / Version / Conventions**: as INT-024, **except `POST /auth/login`, which is the one
unauthenticated route in Prope's management API**. ULID `usr_` ids

**Routes**: `POST /api/v1/auth/login` · `POST /api/v1/auth/logout` · `POST /api/v1/auth/password` ·
`POST /api/v1/workspaces` · `GET|POST /api/v1/workspaces/{id}/members` ·
`DELETE /api/v1/workspaces/{id}/members/{user_id}` · `PUT .../members/{user_id}/roles` ·
`GET|POST /api/v1/prompts/{id}/grants` · `DELETE /api/v1/prompts/{id}/grants/{user_id}` ·
`GET|POST /api/v1/workspaces/{id}/keys` · `DELETE /api/v1/workspaces/{id}/keys/{key_id}` ·
`GET /api/v1/permissions` · `POST /api/v1/users/{user_id}/tombstone` ·
`GET /api/v1/auth/session` · `POST /api/v1/auth/register` ·
`GET /api/v1/auth/workspaces` · `POST /api/v1/auth/workspaces/{workspace_id}/enter` ·
`POST /api/v1/auth/invites/redeem` ·
`GET|POST /api/v1/workspaces/{id}/invites` · `DELETE /api/v1/workspaces/{id}/invites/{invite_id}` ·
`POST /api/v1/workspaces/{id}/members/{user_id}/approve` ·
`POST /api/v1/workspaces/{id}/members/{user_id}/reject`

**Two routes are unauthenticated, not one.** `POST /auth/register` joined `POST /auth/login` with
ADR-0052's SPA: Prope has no outbound channel, so without an open sign-up an install with no accounts
has no way to acquire its first one. There are no others, and
`tests/architecture/test_route_table.py` carries the pair as a named exemption.

**Three routes are reachable from a session that names no workspace** (ADR-0056):
`GET /auth/workspaces`, `POST /auth/workspaces/{workspace_id}/enter` and `POST /workspaces` — plus
`POST /auth/invites/redeem` (ADR-0057). They sit under `/auth` rather than `/workspaces` because each
is a fact about the session's *owner*: there is no tenant in the lobby to hang one off, and the
workspace a redemption reaches is discovered from the code rather than named in the path. Every other
route on this interface answers a lobby session with `403 workspace_required` — not `401`, because the
person is signed in and the client's next move is the chooser.

**`POST /auth/workspaces/{workspace_id}/enter` is the only route in the product that sets the session
cookie after sign-in.** It deletes the presented session row and issues another naming the target,
because a cross-tenant `UPDATE ... SET workspace_id` is refused by row-level security from both sides at
once — the old tenant's `WITH CHECK` refuses the new value and the new tenant's `USING` cannot see the
row.

**The invitation routes carry a credential that crosses exactly once** (ADR-0057). A six-character code
appears in the creation response and nowhere else; only its SHA-256 is stored, and no list route
returns a digest. Every way a redemption can fail — unknown, expired, revoked, exhausted,
rate-limited — answers `404 invite_not_redeemable`, byte for byte.

**`POST /users/{user_id}/tombstone` was added 2026-08-09** when OQ-017 was answered (ADR-0054). It is
the only route in Prope that destroys data, it is irreversible, and it is refused while the person still
holds an active membership. It writes one `user_tombstoned` history event per workspace the person had
been a member of, and **it touches no `history_event` row that already exists** — which is the whole of
the decision.

**Login is rate-limited at 5 failures per email and 20 per source address in a rolling 15 minutes**
([[A-144]]). The limiter is consulted **before the user row is read and before any hash is computed**
(ADR-0043), and **a rate-limited attempt returns the identical response an unknown email and a wrong
password already share** — no distinguishing status, body, header or timing. It is a bounded in-process
structure, so it counts **per process**.

**Passwords are argon2id at `memory_cost=47104` (46 MiB), `time_cost=1`, `parallelism=1`**, with
`check_needs_rehash` on every successful login. **`parallelism=1` is load-bearing** — chosen because of
A-130's co-tenancy on ADR-0033's 4 vCPU.

**`POST /keys` returns the plaintext key in THAT response and nowhere else, ever** ([[A-113]],
ADR-0021). Reads return `id, name, last_four, scope, last_used_at, created_by` — **never the secret**.
Keys are **hashed, never encrypted**.

**`DELETE /keys/{id}` and `DELETE /grants/{user_id}` are effective on the next request** ([[A-114]]) —
nothing is cached, by this module or by any caller. **In the running system.** A restore is not the
running system (ADR-0044, [[A-133]]): `access.session` is excluded from the dump, so a restore
invalidates every session rather than resurrecting revoked ones.

**Grants are rendered by prompt-registry's screen and written here**, because this module owns
`prompt_grant`. The registry does not proxy the write — the SPA calls this route directly. See
**Unmatched pairs** for the lock-file line that still describes it as an in-process command.

**Zero-Admin refusal**: removing a member or revoking a role is **refused if it would leave the
workspace with no Admin** ([[A-117]]).

**`GET /permissions`** returns the `(role, action)` matrix **as data**, so the running matrix can be
read and checked against OQ-006's answer when it arrives.

**Failure semantics**: `401` identical for unknown email, wrong password and rate-limited · `409` on the
zero-Admin refusal, naming the rule · `404` never-forbidden for a subject the actor cannot see · `5xx`
on database failure. **`/readyz` is deliberately NOT gated on property-history** — a permission read
failing closed would take down every module including the gateway (INT-030).

**Idempotency**: none.

**Spec**: generated from FastAPI + pydantic v2 -> OpenAPI.

---

## INT-030 — `GET /healthz`, `GET /readyz`

**Providers**: every module with a process — prompt-registry, evaluation, release-control, gateway,
provider-access, call-ledger, access-control. **property-history exposes neither, deliberately**
**Consumers**: the docker-compose healthcheck, and the operator
**Transport**: HTTP inside the compose network
**Auth**: none
**Version**: unversioned — not under `/api/v1`, by [[A-045]]'s convention

**`/healthz` is process liveness everywhere.** It answers whether the process is running and nothing
else, and must never touch the database, the broker, or another module.

**`/readyz` differs per module, and every difference is a decision**:

| Module | Ready when | Why not more |
|---|---|---|
| gateway | access-control **and** prompt-registry are reachable | call-ledger being unavailable **never** makes the gateway unready — logging is off the response path ([[A-037]]) |
| access-control | the database is reachable | **Not** gated on property-history: a permission read failing closed would take down every module including the gateway. History is required for *writes*, and its unavailability is not a reason to refuse to answer whether someone may *read* |
| provider-access | the **KEK is available** and the database is reachable | A provider being down **never** makes it unready — an unreachable provider is the case the fallback exists for, and reporting it as unreadiness would take the gateway down with it |
| call-ledger | the database is reachable | A **broker outage is degraded-and-counted, not un-ready** — the process can still record every call via the inline fallback, so withholding readiness would take the gateway out of service to protect a path that is working (ADR-0041) |
| prompt-registry, evaluation, release-control | the database is reachable | — |
| **property-history** | **n/a — no route, asserted by a test against the route table** | It has no process of its own; it is a library on the caller's connection (ADR-0023). Mounting any route here reintroduces the access-control cycle A-044 broke, and it would be mounted by somebody reasonable who wants an audit screen ([[A-123]]) |

**The pattern in one line**: a module is un-ready when it cannot do its own job, and never when a
*downstream* module cannot do its. Readiness that cascades converts one module's outage into all of
them, on a host with no HA.

**Failure semantics**: `200` ready, `503` not ready with a body naming the failed check. A `503` on
`/readyz` removes the container from the compose healthcheck's healthy set; **it does not restart the
process** — `/healthz` owns that.

**Spec**: no schema. The contract is the status code and the per-module table above.

---

## Unmatched pairs and open items

Registering thirty seams surfaced **four** places where the lock files and the built system disagree.
None is a gap in the decomposition — every consumed interface has a provider and the one queue has a
publisher — but each is a line that would mislead whoever builds against it.

**1. `authenticate_session()` (INT-005) is exposed with no declared consumer.** No lock file's
`consumes` names it, because its real consumer is a **shared FastAPI session dependency in `app`** used
by all six management surfaces, not any one module. Registered here with that consumer; the honest fix is
one `consumes` line in each of the six locks, or an explicit note that the dependency is shared
infrastructure. **Owed to step 6.**

**2. `visible_subject_filter()` (INT-002) has one declared consumer and two real ones.**
`prompt-registry` declares it. `evaluation`'s security requirements say results are visible to *"exactly
the actors who may read the prompt — same filter, same repository-layer enforcement as the registry"*,
which is this interface, but its `consumes` list names only `may()`. Registered with prompt-registry as
the declared consumer and evaluation flagged, because inventing the second consumer into the registry is
exactly the move this step forbids. **Owed to step 6.**

**3. `call-ledger.lock.yml`'s `events.subscribes` says the wrong thing about evaluation.** It reads
*"The gateway **and evaluation** publish call records here."* Three independent sources say evaluation
does not: its own `events.publishes` is `[]` with a written argument for why; both locks' `inputs` /
`consumes` rows give `price_usage` as an **in-process call**; and `tech_stack.md` calls evaluation *"the
first module to run in `worker` without touching RabbitMQ."* **INT-018 and INT-019 are registered
against that reading** — the queue carries gateway traffic only. The stale clause is prose in one
comment. **Owed to step 6.**

**4. `access-control.lock.yml` describes the grant/revoke commands as an in-process call from
prompt-registry.** They are HTTP routes on access-control (`POST|DELETE /api/v1/prompts/{id}/grants`),
and under ADR-0052 the SPA calls them directly — the registry renders the screen, it does not proxy the
write. Registered at **INT-029**, where the routes actually live. The `transport: in-process call` on
that input row covers `may()` and `visible_subject_filter()` correctly and the grant half loosely.
**Owed to step 6.**

**Not registered, and why**: `/metrics` is declared in no lock file's `apis` block, so registering it
would be inventing a seam into existence. It is a real surface — Caddy routes it to `app:8000` and
Prometheus scrapes it (ADR-0030, ADR-0052) — and it should gain an `exposes` line during step 6 rather
than an INT invented here.

**Also deliberately absent**: `eval_run`'s table claim (ADR-0049) and release-control's hourly sweep
(ADR-0051) are `app` -> `worker` handoffs **within one module**, not across a module boundary. They are
process seams an implementing agent needs and they belong to their own lock files, which already carry
them.

---

## Residual risk

The provider's generated spec fixes the field-level shape; a consumer planned earlier assumed something.
**When two modules on one seam are built far apart in time, re-read this block before building the
second one.** The three seams where that gap is most likely to bite:

- **INT-015 `dispatch()`** — two consumers with opposite responses to the same `DispatchError`, and the
  error taxonomy is the thing both branch on.
- **INT-017 `get_review_summary()`** — `requires_acknowledgement` is computed on one side and enforced
  on the other, with two carve-outs that exist in exactly one place.
- **INT-018's envelope** — the only shape in Prope that can be in flight across a deploy, which is why
  its evolution rule is additive-only rather than a convention.

---

## Diagram

> **Superseded 2026-08-31.** The current diagrams are `docs/architecture/1 - Overall Architecture.html`,
> `docs/architecture/2 - Modules Map.html`, and one page per module under
> `docs/architecture/module-details/` (see its `README.md`). The step-7 outputs described below are
> retired to `docs/architecture/old/` and are no longer re-rendered. The paths in this section point
> there; the counts describe that render, not the current one.

**Re-rendered 2026-08-16 (step 7)** from these thirty-three rows and the eleven lock files:
`docs/architecture/old/module_relationships.excalidraw` (the editable canvas) and
`docs/architecture/old/module_views.html` (the three read-only pages) — **11 modules, 27 module-to-module
edges** (26 sync, 1 async), plus **4 externals and 14 further edges** on the HTML overview.
The HTML carries **11 module-flow tabs** (one per lock file) and **8 user-flow tabs** — UF-1 and UF-2 as
UML use-case diagrams, UF-3 to UF-8 as swimlane activity diagrams.

The 2026-08-09 render covered 8 modules. `prompt-search`, `prompt-conversion` and
`chat-orchestrator` were locked afterwards and are drawn here for the first time.

Both outputs were generated. **The specs they were generated from are checked in beside them** —
`docs/architecture/old/graph.json` and `docs/architecture/old/views.json`. A hand edit to the
`.excalidraw` or the `.html` was discarded silently at the next render.

The commands below are kept for the record; they are not part of the current pipeline:

```bash
python <pack>/skills/bsp-7-diagram/scripts/render_diagram.py \
  --in docs/architecture/old/graph.json --out docs/architecture/old/module_relationships.excalidraw
python <pack>/skills/bsp-7-diagram/scripts/render_views.py \
  --in docs/architecture/old/views.json --out docs/architecture/old/module_views.html
```

| Tag | Module | Tag | Module |
|-----|--------|-----|--------|
| #1 | prompt-registry | #7 | access-control |
| #2 | evaluation | #8 | property-history |
| #3 | release-control | #9 | prompt-search |
| #4 | gateway | #10 | prompt-conversion |
| #5 | provider-access | #11 | chat-orchestrator |
| #6 | call-ledger | | |

**Three registered seams are deliberately not arrows**, because a diagram edge needs a module at both
ends: **INT-005** (the consumer is the shared session dependency in `app`, not any one module — the
same gap this file already owes to step 6), **INT-008** (the consumer is a CI test), and **INT-030**
(the consumers are the compose healthcheck and the operator). Everything else in the registry is drawn.

**Eight arrows are drawn from lock files rather than from this registry**, because two modules have no
INT rows here at all. `prompt-search` (→ prompt-registry, → access-control) and `chat-orchestrator`
(→ access-control, → prompt-search, → prompt-conversion, → prompt-registry) declare their dependencies
in `dependencies:`, `apis.consumes:` and `boundaries.dependency_direction:`, and those declarations are
what the arrows carry. They are drawn **unlabelled**, because no INT id exists to put on them, and the
same gap leaves three page-1 overview edges from the web SPA unlabelled. **This is a step-5 gap, not a
diagram defect**: register the seams and the labels appear at the next render. `prompt-conversion` is
unaffected — INT-001, INT-031, INT-032 and INT-033 cover it, and its arrows carry them.

**Four layout notes from the renderer**, repeated here because a straight arrow cannot dodge and the fix
is a `row` pin nobody has asked for: `#2 evaluation -> #8 property-history` passes over
`#5 provider-access`; `#4 gateway -> #6 call-ledger` passes over `#9 prompt-search`;
`#10 prompt-conversion -> #7 access-control` passes over `#6 call-ledger`; and
`#9 prompt-search -> #7 access-control` passes over `#1 prompt-registry`. All four arrows are correct;
only their routes are awkward. Pin a `row` on one module of any pair in `graph.json` and re-render to
clear them. (The 2026-08-09 warning about `#4 gateway -> #7 access-control` over `#2 evaluation` is
gone — the eleven-module layout resolved it.)

**`module_map.md` still lists eight modules.** The three modules added since have lock files but no row
in the map, no INVEST check and no bounded-context entry. The diagram is drawn from the lock files, so
it is complete; the map is the artifact that is behind.

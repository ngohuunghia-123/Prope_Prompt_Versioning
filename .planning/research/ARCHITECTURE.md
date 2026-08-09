# Architecture: Prope

> Transcribed from `docs/build/gsd_handoff.md` section 3. Not researched by GSD — these are
> decisions already made and traceable to `docs/adr/`.
> Do not revise here; revise upstream and re-run the handoff.

Eight modules across eight bounded contexts. The decomposition follows where the vocabulary changes, not where the deployment artefacts split — there is deliberately no "frontend" or "backend" module, because neither owns a journey. **See the coverage gaps in `PITFALLS.md`: that choice leaves the SPA and the deployment stack without a milestone.**

## Modules

| Module | Does | Kind / size | Depends on |
|--------|------|-------------|-----------|
| prompt-registry | Prompt properties and their immutable revision chain; the diff; search | FEATURE / L | access-control, property-history, provider-access |
| evaluation | Named eval suites; runs candidate against released; cost delta | FEATURE / M | prompt-registry, provider-access, call-ledger, access-control, property-history |
| release-control | Submit → recorded human decision → release, restore, withdraw, break-glass | FEATURE / M | prompt-registry, evaluation, access-control, property-history |
| gateway | OpenAI-compatible `/v1`; resolves a model name to the released revision; fallback | FEATURE / M | prompt-registry, provider-access, call-ledger, access-control |
| provider-access | Workspace provider configs and credentials; **Prope's only outbound egress** | PLATFORM / M | access-control, property-history |
| call-ledger | Every completed call, off the response path; prices, ceilings, retention | PLATFORM / M | none |
| access-control | Authenticates every actor; answers every may-this-actor-do-this question | PLATFORM / S | property-history |
| property-history | The append-only record of every state change; one table, one writer | PLATFORM / S | none |

## Dependency waves and build order

| Wave | Milestone | Module | Phases |
|------|-----------|--------|--------|
| 0 | M1 | call-ledger | 1–3 |
| 0 | M2 | property-history | 4–6 |
| 1 | M3 | access-control | 7–9 |
| 2 | M4 | provider-access | 10–12 |
| 3 | M5 | prompt-registry | 13–15 |
| 4 | M6 | evaluation | 16–18 |
| 4 | M7 | gateway | 19–21 |
| 5 | M8 | release-control | 22–24 |

**Critical path**: property-history → access-control → provider-access → prompt-registry → evaluation → release-control. Six waves.

M1 (call-ledger) and M2 (property-history) have no upstream dependencies and may run in parallel from day one. M6 and M7 are both wave 4 and may run in parallel once M5 and M1 are done.

Wave ordering, readiness, and the critical path are maintained upstream in `docs/build_order.md`.

## The 30 registered seams

21 in-process, 1 broker queue, 6 management API, 2 external HTTP. Full blocks with failure semantics in `docs/architecture/interfaces.md`.

| INT | From → To | Kind | Shape | Notes |
|-----|-----------|------|-------|-------|
| INT-001 | registry, release-control, evaluation, provider-access → access-control | internal | `may(actor, action, subject)` | Fails closed by raising. Closed vocabulary; unknown action → deny |
| INT-002 | prompt-registry → access-control | internal | `visible_subject_filter(actor, subject_type)` | Set form pushed into the caller's own `WHERE` |
| INT-003 | gateway → access-control | internal | `authenticate_api_key(secret)` | Constant-time compare. Never cached, by either side |
| INT-004 | gateway → access-control | internal | `may_resolve(key_id, model_name)` | Default-deny. Refusal returns the same not-found shape as an unknown model |
| INT-005 | every management API → access-control | internal | `authenticate_session(cookie)` | A live row read, not a token verification |
| INT-006 | registry, release-control, evaluation, provider-access, access-control → property-history | internal | `append(event)` | **Runs on the caller's connection inside the caller's open transaction.** Raises; the raise is the mechanism |
| INT-007 | registry, release-control, provider-access → property-history | internal | `read(scope, cursor, limit)` | Ordered by `seq` DESC, never by timestamp |
| INT-008 | CI route-table test → property-history | internal | `registered_actions()` | The 31-action vocabulary as data |
| INT-009 | gateway → prompt-registry | internal | `resolve(model_name, pin)` | The hot path. Must distinguish *name unknown* from *nothing released* |
| INT-010 | gateway → prompt-registry | internal | `list_released(workspace_id)` | Backs `GET /v1/models`. No cursor, no filters, released only |
| INT-011 | evaluation, release-control → prompt-registry | internal | `get_revision`, `get_released_revision`, `get_diff` | Read-only. `get_diff` is `difflib` with `autojunk=False` |
| INT-012 | release-control → prompt-registry | internal | `set_revision_status(version_id, status, decision_id)` | Transition validated by the provider. Keeps ADR-0008 true |
| INT-013 | release-control → prompt-registry | internal | `set_released_revision(prompt_id, version_id, release_id)` | The **only** write to the released pointer. Compare-and-set |
| INT-014 | release-control → prompt-registry | internal | `clear_released_revision(prompt_id, release_id)` | A separate command, not a NULL argument |
| INT-015 | gateway, evaluation → provider-access | internal | `dispatch(...)` | Exactly one attempt. Returns a typed `DispatchError`, never raises on upstream failure |
| INT-016 | prompt-registry → provider-access | internal | `get_model_catalogue(provider_config_id)` | Soft — degrades the picker, never refuses a save |
| INT-017 | release-control → evaluation | internal | `get_review_summary(prompt_id, version_id)` | Read-only pull. Evaluation never calls back |
| INT-018 | gateway → call-ledger | **event** | queue `prope.call_record` | At-least-once, durable, publisher confirms. **Direct PostgreSQL write on a failed confirm.** DLQ `prope.call_record.dlq` |
| INT-019 | evaluation → call-ledger | internal | `price_usage(run_id, usage_rows)` | In-process, **not** the broker. Both sides run in `worker` |
| INT-020 | evaluation → call-ledger | internal | `check_spend_ceiling(workspace_id)` | **Fails OPEN**, counted. Never returns a figure |
| INT-021 | evaluation → call-ledger | internal | `get_run_totals(run_id)` | The two counts are part of the answer, not diagnostics |
| INT-022 | consuming product's SDK → gateway | http | `POST /v1/chat/completions`, `GET /v1/models` | **20 concurrent per key**, OpenAI-shaped 429. Errors OpenAI-shaped, never the management envelope |
| INT-023 | provider-access → the workspace's upstream provider | http | OpenAI-compatible chat completions + model list | **Prope's only outbound egress.** Scheme allow-list, private-range refusal, redirects disabled |
| INT-024 | web SPA → prompt-registry | http | `/api/v1/prompts…`, `/api/v1/revisions…` | 10 routes. Permission filtering in the repository layer via INT-002 |
| INT-025 | web SPA → evaluation | http | `/api/v1/…/eval-suites`, `/api/v1/eval-runs…` | 9 routes. `POST eval-runs` returns 202 + one run id per suite |
| INT-026 | web SPA → release-control | http | `/api/v1/…/submit`, `/approve`, `/releases…`, `/review-tasks…` | 10 routes. Every write appends history in the same transaction |
| INT-027 | web SPA → provider-access | http | `/api/v1/providers…` | 8 routes. **No field, parameter or flag returns a credential** |
| INT-028 | web SPA → call-ledger | http | `/api/v1/prices…`, `/spend-ceiling`, `/retention` | 5 routes. Prices append-only; no body read path exists |
| INT-029 | web SPA → access-control | http | `/api/v1/auth…`, `/workspaces…`, `/grants`, `/keys`, `/permissions` | 15 routes. **5/email, 20/address per 15 min on login** |
| INT-030 | compose healthcheck, operator → every module with a process | http | `GET /healthz`, `GET /readyz` | Readiness differs per module deliberately. property-history exposes neither |

## Three cycles, and how they are broken

1. **prompt-registry ↔ release-control.** Both want the released pointer. Broken by making it a field on the prompt property that only release-control may write, through a command the registry executes.
2. **evaluation ↔ release-control.** Broken by removing the second half: evaluation never calls release-control; release-control pulls run state when it renders.
3. **access-control ↔ property-history.** Broken by giving property-history no standalone UI — the owning module checks permission and then asks for events.

## Forbidden edges

- **call-ledger → anything.** It is a sink. With no edge to access-control it cannot check a permission, so the stored bodies have **no read path in the MVP**.
- **anything → credential.** provider-access is the only module that decrypts anything, into a 60-second in-memory cache and nowhere else.
- **evaluation → gateway.** The eval runner shares the *resolution* semantics, not the module.
- **access-control → anything but property-history.** Callers pass the subject's attributes instead.
- **property-history → anything.** `target_id` and `actor_id` are values, not foreign keys.

## Sources

- `docs/architecture/interfaces.md` — all 30 seams with full failure semantics
- `docs/architecture/module_relationships.excalidraw`, `docs/architecture/module_views.html` — rendered module graph and per-module flows
- `docs/brainstorm/module_map.md` — the decomposition and its bounded-context rationale
- `docs/build_order.md` — wave ordering, readiness, critical path
- `docs/modules/*.lock.yml` — eight lock files, one per module

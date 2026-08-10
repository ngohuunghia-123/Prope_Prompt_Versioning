# Project Research Summary

> Transcribed from `docs/build/gsd_handoff.md` section 5. Not researched by GSD — these are
> decisions already made and traceable to `docs/adr/`.
> Do not revise here; revise upstream and re-run the handoff.

Prope's planning set is unusually complete, and the reason matters for how it should be built.

**The enforcement pattern is the project's spine.** Six times, a rule that could have lived in application code was pushed into the database instead: BR-03's Approved-only released pointer is a **constraint**; the append-only history is a **privilege** (`REVOKE UPDATE, DELETE`); tenant isolation is a **policy** (RLS, deny-by-default, a missing filter returns zero rows); schema-per-module is a **grant**; `search_text` is a **trigger**; and ADR-0045 inverted the RLS coverage test so it walks every table in all eight schemas and demands each be tenant-scoped or declared global with a written reason. That inversion caught `registry.revision` — the table holding every prompt body — on day one, with no new decision required. **Build in that order: the migration carries the guarantee, and the application code is what the guarantee protects.** Four tables gained a `workspace_id` column this way across six passes.

**Everything asynchronous was refused except one thing.** There is exactly one broker queue, `prope.call_record`, and it exists because writing a call record must not sit on the response path. Cache invalidation over the broker was proposed twice and rejected twice on merit: the gateway's 30 s resolution cache **expires**, it is never invalidated, and the release UI says so. Evaluation declines the broker because `eval_run.status` is already a queue and a redelivered message would re-dispatch every case on the workspace's own key. Do not add a second queue, and do not add fanout invalidation.

**Permission is a local decision with the subject passed in.** access-control may not read any subject it authorises, so callers pass `owner_id` and `access_level` from the row they already read. That one signature is what keeps access-control's dependency list at a single entry and makes the six would-be back-edges unnecessary rather than merely prohibited. The set form, `visible_subject_filter(actor, subject_type)`, exists because without it "permission filtering lives in the repository layer" cannot be kept without a cross-module join — and the version that ships under deadline pressure is the query with no filter at all.

**Refusal shapes carry security weight.** Not-found when the actor cannot see the subject; forbidden naming the missing permission when they can. A key-scope refusal is byte-identical to an unknown model name so a leaked key cannot enumerate the registry. A rate-limited login is byte- and timing-identical to a wrong password. These are asserted, not intended.

**What is genuinely unestimated** is narrow and named: streaming wire-compatibility with accumulate-after-close logging, where the sharp edge is the first-byte boundary (the fallback is reachable on one side and not the other); and the p95 50 ms gateway budget, which is an agent-placed placeholder until OQ-012's number arrives. The instrumented span exists either way, so the first load test replaces a placeholder rather than starting an argument about how to measure it.

**The one thing the planning set does not contain is a plan for anything that is not a module** — see `PITFALLS.md`, coverage gaps 3 and 4.

## Key Findings

1. **Build database-first, every phase.** The migration carries the guarantee; the application code is what the guarantee protects. A phase that writes the service layer before the constraint, privilege, policy, grant, or trigger has built the wrong thing in the right order.
2. **One broker queue, ever.** `prope.call_record` and its DLQ. A second queue or any fanout invalidation contradicts a decision that was made twice on merit.
3. **access-control never reads its subjects.** Callers pass `owner_id` and `access_level` in. This is what keeps its dependency list at one entry.
4. **Refusal shapes are security properties.** Not-found vs. forbidden, and byte-and-timing identity for key-scope and rate-limited-login refusals, are asserted by tests — not left to convention.
5. **Two things are genuinely unestimated**: mid-stream failure semantics around the first-byte boundary (phase 21), and the p95 50 ms gateway budget (a placeholder until OQ-012).
6. **The plan covers modules and nothing else.** The React SPA (57 routes across six modules) and the whole deployment stack (7 services, 2 images, CI/CD, backups, monitoring) belong to no milestone. This is the largest structural gap and needs a user decision.
7. **Sixteen acceptance criteria are owed and were never written as rows**, and eight more assert against infrastructure that step 4 replaced. Both sets are catalogued in `PITFALLS.md` with the phase that should absorb each.

## Implications for Roadmap

- **The roadmap is adopted, not derived.** 8 milestones (one per module), 24 phases numbered continuously 1–24, three phases per module collapsing the seven-phase spine into `A+B` (data model and core logic), `C+D` (exposed and consumed seams), `E+F+G` (resilience, observability, security, acceptance closeout).
- **Two entry points, not one.** M1 (call-ledger, phases 1–3) and M2 (property-history, phases 4–6) are both wave 0 with no upstream dependencies and may run in parallel from day one. M6 (evaluation) and M7 (gateway) are both wave 4 and may run in parallel once M5 and M1 are done.
- **The critical path is six waves**: property-history → access-control → provider-access → prompt-registry → evaluation → release-control.
- **The first phase of each module is a migration phase.** Every module's phase A+B is schema, RLS, constraints, triggers, and privileges before anything else.
- **prompt-registry (M5, phases 13–15) is the schedule risk.** The only `L` module and the widest surface; if it stalls, nothing downstream can be demonstrated. Its internal sequencing is already fixed: property + revision + activity, then search and filter, then diff.
- **Phases 22–24 are the only place the cross-module route-table tests can run**, because they assert properties of the *assembled* route table and every module must be mounted first.
- **Two decisions are owed before the pilot, not before the build**: whether the SPA gets a ninth milestone or per-milestone UI phases, and whether the deployment stack gets its own milestone. Neither blocks phase 1.
- **Phase plans must use the restated form of the eight stale acceptance criteria** in `PITFALLS.md` section 2, not the lock files' literal text.

## Sources

Upstream planning artifacts, not web sources.

| Artefact | What it carries |
|----------|-----------------|
| `docs/build/gsd_handoff.md` | The handoff itself (bsp-gsd/1) — the authoritative input to this adoption |
| `docs/architecture/interfaces.md` | All 30 seams with full failure semantics |
| `docs/architecture/tech_stack.md` | Per-module stack rows, `Inherited` vs `Deviated`, with rejected alternatives |
| `docs/adr/` | 54 ADRs; `docs/adr/adr_index.md` is the index |
| `docs/modules/*.lock.yml` | Eight lock files — scope, surface, data, dependencies, failure modes, acceptance criteria, test plan |
| `docs/brainstorm/assumptions/` | 151 assumption files — the source of truth over the index table |
| `docs/brainstorm/00_context.md` | Problem, users, success, scope, constraints, glossary |
| `docs/brainstorm/module_map.md` | The decomposition and its bounded-context rationale |
| `docs/brainstorm/open_questions/` | OQ-005, OQ-006, OQ-008, OQ-012, OQ-013 |
| `docs/AGENT_CONTEXT.md` | The BSP sweep's own digest, regenerated at step 6 |
| `docs/build_order.md` | Wave ordering, readiness, and the critical path |

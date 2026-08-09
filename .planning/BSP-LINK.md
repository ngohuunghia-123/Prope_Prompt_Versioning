# Planning handoff link

> Generated from `docs/build/gsd_handoff.md` (bsp-gsd/1) on 2026-08-09. Do not hand-edit.

| Phase | Milestone | Module | Read before planning this phase |
|-------|-----------|--------|----------------------------------|
| 1 | M1 | call-ledger | `docs/modules/call-ledger.lock.yml`, `docs/architecture/interfaces.md` |
| 2 | M1 | call-ledger | `docs/modules/call-ledger.lock.yml`, `docs/architecture/interfaces.md` |
| 3 | M1 | call-ledger | `docs/modules/call-ledger.lock.yml`, `docs/architecture/interfaces.md` |
| 4 | M2 | property-history | `docs/modules/property-history.lock.yml`, `docs/architecture/interfaces.md` |
| 5 | M2 | property-history | `docs/modules/property-history.lock.yml`, `docs/architecture/interfaces.md` |
| 6 | M2 | property-history | `docs/modules/property-history.lock.yml`, `docs/architecture/interfaces.md` |
| 7 | M3 | access-control | `docs/modules/access-control.lock.yml`, `docs/architecture/interfaces.md` |
| 8 | M3 | access-control | `docs/modules/access-control.lock.yml`, `docs/architecture/interfaces.md` |
| 9 | M3 | access-control | `docs/modules/access-control.lock.yml`, `docs/architecture/interfaces.md` |
| 10 | M4 | provider-access | `docs/modules/provider-access.lock.yml`, `docs/architecture/interfaces.md` |
| 11 | M4 | provider-access | `docs/modules/provider-access.lock.yml`, `docs/architecture/interfaces.md` |
| 12 | M4 | provider-access | `docs/modules/provider-access.lock.yml`, `docs/architecture/interfaces.md` |
| 13 | M5 | prompt-registry | `docs/modules/prompt-registry.lock.yml`, `docs/architecture/interfaces.md` |
| 14 | M5 | prompt-registry | `docs/modules/prompt-registry.lock.yml`, `docs/architecture/interfaces.md` |
| 15 | M5 | prompt-registry | `docs/modules/prompt-registry.lock.yml`, `docs/architecture/interfaces.md` |
| 16 | M6 | evaluation | `docs/modules/evaluation.lock.yml`, `docs/architecture/interfaces.md` |
| 17 | M6 | evaluation | `docs/modules/evaluation.lock.yml`, `docs/architecture/interfaces.md` |
| 18 | M6 | evaluation | `docs/modules/evaluation.lock.yml`, `docs/architecture/interfaces.md` |
| 19 | M7 | gateway | `docs/modules/gateway.lock.yml`, `docs/architecture/interfaces.md` |
| 20 | M7 | gateway | `docs/modules/gateway.lock.yml`, `docs/architecture/interfaces.md` |
| 21 | M7 | gateway | `docs/modules/gateway.lock.yml`, `docs/architecture/interfaces.md` |
| 22 | M8 | release-control | `docs/modules/release-control.lock.yml`, `docs/architecture/interfaces.md` |
| 23 | M8 | release-control | `docs/modules/release-control.lock.yml`, `docs/architecture/interfaces.md` |
| 24 | M8 | release-control | `docs/modules/release-control.lock.yml`, `docs/architecture/interfaces.md` |

## Always worth reading once

- `docs/AGENT_CONTEXT.md` — what this project is, where things live
- `docs/adr/` — the why behind a constraint that looks surprising (`docs/adr/adr_index.md` is the index)
- `docs/build_order.md` — wave ordering, readiness, and the critical path
- `docs/brainstorm/00_context.md` — problem, users, success, scope, constraints, glossary

## Before planning any phase

- **`bsp-build-tasks <module_id>`** generates the ordered implementation task list for that module — run it when the module's turn arrives, not before. Tasks depend on what the earlier modules actually turn out like.
- **Check `.planning/research/PITFALLS.md` gaps 1 and 2** for this phase. Sixteen acceptance criteria are owed and were never written as rows, and eight more assert against infrastructure a later decision replaced. **Plan against the restated form, not the lock file's literal text.**

## Out of bounds

Applies to every milestone:

- Do not edit `docs/modules/*.lock.yml`, `docs/architecture/*`, or any ADR.
- Do not depend on a module outside the milestone's `dependencies[]`.
- Do not write to a table outside that module's `data.owns[]`.
- Do not expose an API or event outside its `apis.exposes[]` / `events.publishes[]`.

If one of those turns out to be necessary, that is real information — the spec is wrong. Stop, write an `OQ-NNN` naming the exact lock file field and the conflict, and say so. **Do not edit the spec to match the code you were about to write.**

# Build order

> Derived from `dependencies[]` across `docs/modules/*.lock.yml`.
> Regenerate when a dependency changes.
> Milestone and phase columns filled by `bsp-build-tasks --handoff` on 2026-08-09.

| Wave | Modules | Milestone | Phases | Why |
|------|---------|-----------|--------|-----|
| 0 | call-ledger | M1 | 1–3 | no upstream dependencies — it is a sink |
| 0 | property-history | M2 | 4–6 | no upstream dependencies — the only module with an empty `consumes` list |
| 1 | access-control | M3 | 7–9 | needs property-history (INT-006) |
| 2 | provider-access | M4 | 10–12 | needs access-control (INT-001), property-history (INT-006) |
| 3 | prompt-registry | M5 | 13–15 | needs access-control (INT-001, INT-002), property-history (INT-006, INT-007), provider-access (INT-016) |
| 4 | evaluation | M6 | 16–18 | needs prompt-registry (INT-011), provider-access (INT-015), call-ledger (INT-019/020/021), access-control (INT-001), property-history (INT-006) |
| 4 | gateway | M7 | 19–21 | needs prompt-registry (INT-009, INT-010), provider-access (INT-015), call-ledger (INT-018), access-control (INT-003, INT-004) |
| 5 | release-control | M8 | 22–24 | needs prompt-registry (INT-011–014), evaluation (INT-017), access-control (INT-001), property-history (INT-006, INT-007) |
| 2 | prompt-observation | — | — | needs access-control (INT-001) and nothing else. **Blocked on OQ-147, not on a dependency** — see below |

**Critical path**: property-history → access-control → provider-access → prompt-registry → evaluation
→ release-control (6 waves; the longest chain, and the one to start first).

**Parallelism available**: call-ledger (M1) runs alongside the whole critical path and is only needed
by wave 4. evaluation (M6) and gateway (M7) share wave 4 and can be built concurrently once M5 and M1
are done.

**Ready**: all eight of the original set — `ready_for_build: true` as of 2026-08-09.
**Not ready**: `prompt-observation`, added 2026-08-18 by ADR-0060.

**`prompt-observation` sits in wave 2 by dependency and nowhere by schedule.** Its only upstream is
access-control, so it *could* be built the moment wave 1 lands — earlier than the gateway that feeds it,
which is unusual and correct, because the gateway's half of ADR-0059 is one branch and a nullable column
while this module is the part with tables in it. What holds it is **OQ-147**: whether the pilot may
observe real production traffic at all, which is A-020's line and not a technical dependency. The
gateway's own change is unaffected and ships inside M7 — `observe_provider_config_id` is NULL on every
key, so the mode is inert until somebody sets it and OQ-147 decides whether anybody may.

**This table lists nine of twelve locks.** `prompt-conversion`, `prompt-search` and `chat-orchestrator`
have lock files and no row here, the same drift `module_map.md` and `interfaces.md` both now record.
Regenerating this file properly is a step-2 pass nobody has run.

---

## Generating tasks

Tasks are deferred on purpose: a task list written today for a module built in six weeks is a plan you
have to un-learn. Generate them one module at a time, when that module's turn arrives:

```text
bsp-build-tasks call-ledger        # wave 0 — start here, or:
bsp-build-tasks property-history   # wave 0 — start here (critical path)
```

Both wave-0 modules are safe to start now. Nothing else is.
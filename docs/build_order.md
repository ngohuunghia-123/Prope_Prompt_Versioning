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
| 5 | prompt-readiness | — | — | needs prompt-registry (INT-011, INT-037), evaluation, provider-access (INT-015), access-control (INT-001), call-ledger write side. **Ready, and later than its dependencies rather than blocked by a question** |
| 6 | prompt-improvement | — | — | needs prompt-readiness (the probe runner), prompt-registry (INT-043, INT-044), evaluation (the gate), provider-access, access-control, property-history. **The deepest module in the graph** — the only one that depends on another feature module |

**Critical path**: property-history → access-control → provider-access → prompt-registry → evaluation
→ release-control (6 waves; the longest chain, and the one to start first).

**Parallelism available**: call-ledger (M1) runs alongside the whole critical path and is only needed
by wave 4. evaluation (M6) and gateway (M7) share wave 4 and can be built concurrently once M5 and M1
are done.

**Ready**: all eight of the original set — `ready_for_build: true` as of 2026-08-09, plus
`prompt-readiness` and `prompt-improvement` as of 2026-08-20.
**Not ready**: `prompt-observation`, added 2026-08-18 by ADR-0060.

**`prompt-observation` sits in wave 2 by dependency and nowhere by schedule.** Its only upstream is
access-control, so it *could* be built the moment wave 1 lands — earlier than the gateway that feeds it,
which is unusual and correct, because the gateway's half of ADR-0059 is one branch and a nullable column
while this module is the part with tables in it. What holds it is **OQ-147**: whether the pilot may
observe real production traffic at all, which is A-020's line and not a technical dependency. The
gateway's own change is unaffected and ships inside M7 — `observe_provider_config_id` is NULL on every
key, so the mode is inert until somebody sets it and OQ-147 decides whether anybody may.

**`prompt-readiness` sits in wave 5 and is ready.** It is the deepest module in the graph — it needs
prompt-registry's body and profile, evaluation's assertion compiler, provider-access's dispatch and
call-ledger's ceiling, so it cannot start before wave 4 completes. Unlike `prompt-observation` nothing
external holds it: OQ-157 is non-blocking and bites the *second* version of the rule catalogue rather
than the first. Its sibling `prompt-improvement` gained both a row and a lock on 2026-08-20, and the sentence that
used to stand here — *"OQ-154 blocks it entirely"* — was **wrong about the consequence while being
right about the data**. OQ-154 is real: tool errors and retrieval failures have nowhere in Prope to
live, so tier 3 of the original design cannot be built. ADR-0068 declares that tier a NON-GOAL rather
than deferred scope (SR-8), which is the whole reason the original module was split in two: a lock
whose scope is half-blocked is a lock nobody trusts, and this table cannot represent one. The other
two tiers — metadata detectors and scheduled re-probing — depend on nothing OQ-154 owns.

**`prompt-improvement` sits in wave 6 and is the only module that depends on another FEATURE module.**
Every other edge in this graph runs into a platform concern; this one runs into `prompt-readiness`, for
the probe runner and the finding vocabulary. That is deliberate rather than convenient: a second
dispatch loop would be a second definition of *"refused 11 of 12"*, and the comparison the scheduled
re-probe exists to make would be meaningless if the two sides measured different things. It also cost
`prompt-readiness` its leaf status, which its `seams.py` docstring now records.

**This table lists eleven of fourteen locks.** `prompt-conversion`, `prompt-search` and `chat-orchestrator`
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
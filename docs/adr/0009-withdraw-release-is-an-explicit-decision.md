# ADR-0009 — Withdrawing a release is an explicit recorded decision, and the gateway then fails loudly

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-069)
**Module**: release-control, prompt-registry, gateway (written while locking release-control)
**Related**: A-022, A-031, A-049, A-052, A-069, ADR-0001, ADR-0007

## Context

A-052 was recorded while locking prompt-registry: retiring a prompt property is refused while it has an
active release, because `00_context.md#constraints` accepts Prope as a **hard dependency** of consuming
products' request paths. Under that constraint, removing a prompt from production is an outage in
somebody else's product, and it must not be reachable by an owner tidying up a list.

A-052 closed the retire path by naming an action that did not exist anywhere: *"the release must first
be withdrawn — a recorded decision on release-control's surface"*. Its own impact note flagged the
discovery and deferred confirmation to this lock. This ADR confirms it and settles two things A-052 left
unstated: how the pointer is cleared, and what the gateway does afterwards.

`prompt-registry.lock.yml` exposes `set_released_revision(prompt_id, version_id, release_id)`, whose
target must be an Approved revision — enforced by a database constraint (BR-03). There is no shape in
that command for "no revision at all".

## Decision

**Withdraw is a kind of release** (`release.kind = withdraw`), with `version_id` NULL and
`previous_version_id` naming what was taken out of production. It reuses the release log rather than
creating a fourth entity (ADR-0007), so one query answers "what has been in production, and when".

It carries:

- **its own permission**, distinct from release — holding release does not confer withdraw;
- **a mandatory reason**;
- **a confirmation naming the model name**, so the actor reads the string other people's code is
  calling, not a title;
- **a `release_withdrawn` history event** with an actor on it.

The pointer is cleared through a new prompt-registry command,
`clear_released_revision(prompt_id, release_id)`. It is a separate command rather than
`set_released_revision(..., NULL)` so that the Approved-only database constraint keeps applying with no
NULL carve-out — the constraint that stops unapproved text reaching production is the last one that
should learn a special case.

**Afterwards the gateway fails loudly.** A bare model name with no released revision returns a
model-not-found error in the OpenAI error shape. It does not serve the previously released revision, and
it does not serve the fallback answer — a fallback covers an upstream provider failure (A-034), not a
deliberate withdrawal. A-022 already forbids falling back to another revision; this is the same rule
reaching its logical end.

## Alternatives rejected

**Let retire cascade — retiring a prompt clears its own release.** The convenient answer, and rejected
because it is precisely the silent production break A-052 exists to prevent. The person tidying their
list sees a confirmation about a registry entry; the consequence lands in a service they have never
heard of. Two deliberate acts by someone holding two different permissions is the whole point.

**Keep serving the last released revision after a retire or withdrawal**, treating the pointer as a
cache of last resort. Rejected: it makes "retired" mean nothing operationally, and it produces the worst
possible failure — a prompt that is retired in the registry, unowned, unreviewed, and still answering
production traffic. Every screen would say it is gone.

**Soft-delete with a grace period** — withdraw schedules removal in 7 days and traffic drains
meanwhile. Rejected: it needs a scheduler nobody is watching, in a system with no broker and no worker
fleet (A-012), and the grace period would end at some hour when nobody is looking. It converts one
loud, attributable failure into a quiet one on a timer. A hard dependency deserves the loud version.

**Serve the fallback answer instead of an error.** Rejected: it would report a withdrawal as an upstream
outage. The fallback is detectable by the caller (`x-prope-fallback`), but the consuming team would read
"the provider is having trouble" when the truth is "someone in your organisation removed this prompt
from production", and they would debug the wrong system.

## Consequences

- `prompt-registry.lock.yml` gains `clear_released_revision` and an amended note on the released-pointer
  field; the map's release-control → prompt-registry seam now lists three commands, not one.
- The gateway's resolve path must distinguish "model name unknown" from "model name known, nothing
  released". Both return not-found to the caller, but only the second is a withdrawal, and the two must
  be separable in `prope_registry_resolve_miss_total` — otherwise a withdrawal is invisible in the one
  metric that would show its blast radius. To be honoured when the gateway is locked.
- The gateway's 30 s resolution cache (A-031) ~~invalidates on withdrawal exactly as it does on
  release~~ **expires**, so the outage begins within one cache window rather than at an unpredictable
  moment. *Corrected 2026-08-09 during release-control's stack pass* — ADR-0012 established that nothing
  invalidates that cache, and this line was written before it. **The property this bullet asked for is
  unchanged and is delivered**: bounded, always within 30 seconds, with no coordination between
  processes. Only the mechanism named here was wrong. See the amendment below for what that costs the
  word *"loudly"* in this ADR's title.
- Withdraw and then release-again is an ordinary release of an Approved revision. Nothing special is
  needed to undo a withdrawal, which is the property that makes the loud version safe to choose.
- **Stated limitation, not mitigated**: the confirmation cannot tell the actor how much traffic that
  model name is currently taking, because release-control does not read the call ledger and that edge is
  forbidden (the ledger is a sink). The actor is told what they are turning off, not how loudly it will
  be missed. Opening that read is a seam change and belongs to a later decision, with OQ-013 settled
  first.

---

## Amendment, 2026-08-09 (step 4, release-control's stack pass) — "loudly" is up to 30 seconds late, and the alternative was re-argued

**Nothing in the decision changes.** Withdraw is still a kind of release, still carries its own
permission, its own mandatory reason, a confirmation naming the model name, and a `release_withdrawn`
event with an actor on it. The gateway still returns model-not-found and still refuses to serve the
previous revision or the fallback answer.

What is corrected is the timing this ADR implied. **The withdrawal is loud, but it is not immediate.** A
gateway process holding a warm entry keeps serving the withdrawn revision until that entry expires —
**up to 30 seconds** (ADR-0012). Three places said otherwise and are fixed in this pass:

- `release-control.lock.yml`'s withdraw failure mode claimed the resolve-miss counter *"rises
  immediately"*;
- its `forbidden_dependencies` entry for the gateway justified the forbidden edge partly on *"the
  gateway's cache invalidates itself from the registry write"*;
- **AC-7 asserts the gateway returns model-not-found with no tolerance stated** — as written, an e2e test
  that fails or passes depending on cache age. Restatement recorded as owed to the step-6 sweep.

### The broker alternative was reconsidered on merit and still loses

ADR-0012 rejected pub/sub invalidation with an explicit caveat about its own reasoning: *"**Rejected by
A-012 before it is rejected on merit**: the system must come up with one `docker-compose up` for a team
with no dedicated ops."* **ADR-0028 removed that premise** — RabbitMQ is in the stack. So the rejection had
to be re-made rather than inherited, and this ADR is where it matters most, because withdrawal is the one
action whose whole purpose is to stop production traffic.

It was re-made and the answer is the same. A fanout exchange with a per-process exclusive queue would
evict on withdrawal — and it would fire **only** on withdrawal, the rarest action in the product. That is
this project's own standing objection, now used for the third time: ADR-0041 deleted the spill file
because *"the mechanism most likely to be wrong is the one exercised least — a spill path that only runs
during an incident is a path nobody has watched work,"* and ADR-0012's own gateway-pass amendment deleted
stale-if-error on the same ground one pass ago. It would also make `app` a broker consumer for the first
time, inside the process holding the only Success-metric latency budget in the build, and it would not
close the window anyway: a restarted process, a cold consumer, or A-130's split each leave a TTL to serve
out.

Against 30 seconds of exposure on an operation whose own stated target is **five minutes** (H-05,
`00_context.md#success`), the mechanism earns nothing it does not already have.

### What the 30 seconds actually costs, stated plainly

The consuming product keeps receiving correct, approved answers from a revision that was deliberately
taken out of production, for less than half a minute, and then receives a clear model-not-found. The
safety property ADR-0012 rests on holds throughout: **a cached entry can only ever serve a revision that
was released, and the released pointer can only ever have pointed at an Approved revision** — a database
constraint (BR-03, ADR-0001). Staleness delays a withdrawal; it cannot put unapproved text into
production.

**The withdraw screen owes the same sentence the release screen already owes**: *takes effect within 30
seconds*. An operator who withdraws, refreshes a consumer's dashboard, sees traffic still flowing and
concludes the withdrawal failed will withdraw again — and the second act is the one that gets recorded
without a reason worth reading.

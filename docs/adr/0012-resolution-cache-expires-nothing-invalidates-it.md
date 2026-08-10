# ADR-0012 — The resolution cache expires; nothing invalidates it

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-080)
**Module**: gateway, prompt-registry (written while locking gateway)
**Related**: A-012, A-031, A-041, ADR-0001, ADR-0009
**Supersedes**: the "invalidated immediately on release or restore" clause of A-031

## Context

A-031 says the gateway caches resolutions for 30 seconds and that the cache is "invalidated
immediately on release or restore". `prompt-registry.lock.yml` restates it from the other side: "the
gateway's 30 s resolution cache invalidates itself on the released-pointer write".

Neither sentence describes a mechanism, and when this lock was written the mechanism turned out not to
exist. The write happens inside prompt-registry, in a transaction started by a release-control
command. The cache lives in the gateway's process memory. Between them sit three constraints:

- **prompt-registry → gateway is a forbidden edge.** A registry that calls the gateway puts a
  management surface inside a latency-critical path (`prompt-registry.lock.yml`).
- **There is no message broker.** A-012 caps the system at one `docker-compose up` for a team with no
  dedicated ops.
- **The cache exists to remove a database read from the hot path.** Any invalidation scheme that
  reintroduces a per-request read has deleted the reason for the cache while keeping its complexity.

"Invalidates itself on someone else's write" is not something a cache can do. The clause was written
as an intention and it needs a decision.

## Decision

**The TTL is the only mechanism. Nothing invalidates the cache.**

- A bounded LRU of at most 5,000 entries, keyed by `(workspace_id, model_name, pin)`, TTL 30 s.
- A release, a restore, or a withdrawal sends no message anywhere. It becomes visible when the entry
  expires — **within 30 seconds, always, with no coordination between processes**.
- The 30 s window is stated in words on the release and withdraw screens, rather than implied to be
  instant.
- **Stale-if-error**: when prompt-registry is unreachable, an expired entry may continue to be served
  for up to 5 minutes, marked `prope.stale_resolution: true`, counted by
  `prope_gateway_stale_resolution_total`, and paging on the first occurrence.

The safety property that makes this acceptable: **a stale entry can only serve a revision that was
released, and the released pointer can only ever have pointed at an Approved revision** — a database
constraint, not application code (BR-03, ADR-0001). Staleness can therefore delay a change; it cannot
put unapproved text into production. That is the difference between a bounded annoyance and the one
failure that makes the product worthless.

The budget says this is affordable. The restore target is ≤ 5 minutes end to end (H-05,
`00_context.md#success`); 30 seconds of it spent in a cache leaves roughly 10× headroom.

## Alternatives rejected

**The registry pushes an invalidation to the gateway.** Rejected: it reverses a forbidden edge. Even
implemented as a callback the registry holds rather than a module dependency, it means a management
write now has a runtime coupling to the hot path — a slow or wedged gateway becomes a slow release,
and the release transaction acquires a reason to fail that has nothing to do with releasing.

**A generation counter the gateway reads per request** — one indexed row per workspace, bumped on
every pointer write. Rejected: at 50 rps this is a database round trip on every call, which is the
exact cost the cache was built to remove. It trades a 30-second staleness window for a permanent
latency floor inside a 50 ms budget.

**A message broker or a pub/sub channel.** Rejected by A-012 before it is rejected on merit: the
system must come up with one `docker-compose up` for a team with no dedicated ops. Adding a broker to
save 30 seconds on an operation with a 5-minute target is the definition of a moving part that earns
nothing.

**A much shorter TTL — 1 to 5 seconds.** Rejected: it does not remove the class of problem, it shrinks
the window while multiplying registry reads by six to thirty. The staleness is either acceptable or it
is not; if it is not, the answer is a mechanism, not a smaller number.

**No cache at all.** Honest, and it was seriously considered — the registry budgets `resolve()` at p95
< 10 ms, which fits inside 50 ms. Rejected because it makes every gateway call a database call, so the
database's availability becomes the gateway's availability on a path the constraints table has already
accepted as a hard dependency of other people's production traffic. The cache is also what makes
stale-if-error possible, and that is the only thing in this module that narrows the Prope-outage hole
OQ-012 leaves open.

**Fail closed instead of serving stale when the registry is down.** Rejected as the trade the
hard-dependency constraint forbids: a registry blip would become a full outage in every consuming
product. The cost is stated rather than hidden — see below.

## Consequences

- A-031's invalidation clause is superseded. The 30 s TTL and the p95 50 ms placeholder survive
  unchanged; only "invalidated immediately" is withdrawn. A-031 carries a dated amendment note.
- `prompt-registry.lock.yml`'s `events.subscribes` comment is corrected: the registry does not notify
  the gateway, and the gateway does not invalidate — the entry expires.
- ADR-0009 asked that a withdrawal begin "within one cache window rather than at an unpredictable
  moment". That is now exactly what happens, and it is the mechanism rather than an aspiration.
- **Stated cost, not mitigated**: during a registry outage, stale-if-error keeps a withdrawn or
  restored binding alive for up to 5 minutes — the two moments when serving the previous revision is
  least wanted. The window is bounded, counted, and pages on the first occurrence, so it is never
  silent. The alternative is a full outage of every consuming product, which is the worse trade under
  an accepted hard dependency.
- The release UI now owes a sentence: "takes effect within 30 seconds". A release screen that implies
  instant effect would make an operator refresh a consumer's dashboard and conclude the release failed.
- Horizontal scaling stays trivial. There is no invalidation fan-out, so a second gateway process is a
  second process and nothing else — which is what A-012 asks of every part of this system.

---

## Amendment, 2026-08-09 (step 4, gateway's stack pass) — stale-if-error is deleted, and two of this ADR's arguments are withdrawn

**The core decision is unchanged and is not reopened.** The TTL is still the only mechanism, nothing
still invalidates the cache, a release is still visible within 30 seconds with no coordination between
processes, and the safety property that makes it acceptable — *a stale entry can only serve a revision
that was released, and the released pointer can only ever have pointed at an Approved revision, by
database constraint* — is untouched. AC-9, the e2e script, and the *"time for a released-pointer change
to be served by every gateway process ≤ 30 s"* performance row all stand as written.

What is withdrawn is **stale-if-error**, and with it two of the three arguments this ADR used to justify
the cache. Both were falsified by decisions taken after it, in other modules' passes.

### 1. "The database's availability becomes the gateway's availability" — already true, cache or no cache

This ADR rejected *"No cache at all"* on the ground that it *"makes every gateway call a database call,
so the database's availability becomes the gateway's availability on a path the constraints table has
already accepted as a hard dependency of other people's production traffic."*

That property does not belong to this cache. The gateway's own security requirement is that *"every
request authenticates a consumer key through access-control before any registry read"*, and **A-114 and
ADR-0022 forbid caching either of the two calls that does** — `authenticate_api_key` and `may_resolve` —
on both sides of the seam, because a stale permission is a revoked key still working. So every gateway
request already makes two uncacheable database reads before this cache is consulted. **A cache cannot
protect an availability property that two reads ahead of it have already spent.**

### 2. Stale-if-error's trigger is a state the architecture no longer permits

The mechanism reads: *"when prompt-registry is unreachable, an expired entry may continue to be served
for up to 5 minutes."* Under ADR-0026 and ADR-0033, **prompt-registry is an in-process function call in
the same container** — there is no seam across which it can be unreachable. "Unreachable" resolves to
*the database is unreachable*, and authentication reaches that database first, cannot be cached, and
fails first. The request returns 401/503 at the auth step and the stale entry is never consulted.

The consequence paragraph above — *"during a registry outage, stale-if-error keeps a withdrawn or
restored binding alive for up to 5 minutes"* — therefore describes a window that cannot open, and this
ADR's closing claim that stale-if-error is *"the only thing in this module that narrows the
Prope-outage hole OQ-012 leaves open"* is withdrawn. It narrows nothing.

One crack survives: a lock or a slow query on `registry.prompt_property` **specifically**, while
`access.*` reads stay healthy — realistically ADR-0031's migration window, which is also the moment the
process holding the warm cache is about to restart and lose it. That is not enough to keep a mechanism
for, on this project's own stated precedent: ADR-0041 deleted the spill file because *"the mechanism most
likely to be wrong is the one exercised least — a spill path that only runs during an incident is a path
nobody has watched work."*

### What is deleted

- the 5-minute stale-if-error window (A-080 is amended in the same pass)
- `prope_gateway_stale_resolution_total`
- the `GatewayStaleResolution` alert, which **pages** — for a state that cannot be reached
- the `cache = stale` label on `prope_gateway_resolve_duration_seconds`
- the *"prompt-registry is unreachable or slow"* failure mode, and the risk row about stale-if-error
  keeping a withdrawn binding alive
- the chaos test *"prompt-registry killed mid-traffic"* — it cannot be performed, because killing
  prompt-registry means killing the database, at which point authentication fails first

### What the cache now rests on, in full

**Latency, and nothing else.** prompt-registry budgets `resolve()` at p95 < 10 ms against a 50 ms
gateway budget — and that 50 is, in A-031's own words, an agent-decided placeholder OQ-012 has never
replaced. So the honest statement is that this cache buys a fifth of an unvalidated budget, on the one
path `00_context.md#constraints` treats as a hard dependency of other products' request traffic.

**Deleting it outright was seriously considered in this pass and rejected on asymmetry, not on merit.**
The failure mode of keeping the cache is a bounded, counted, documented 30-second delay against a
5-minute restore target — 10× headroom, as originally argued. The failure mode of deleting it is a
latency regression against a budget nobody has measured, on a path other teams' production traffic
depends on; and it would put an immediacy promise on the release screen that re-adding the cache later
would have to walk back. Being wrong about 30 seconds of staleness is recoverable. Being wrong about
latency on a hard dependency is an incident in somebody else's product.

**This is the third mechanism in three consecutive module passes found resting on a premise a later
decision had removed** — prompt-registry's model-catalogue cache (deleted), A-063's dispatch clause
(deleted), and stale-if-error (deleted here). All three were written while the architecture was still
"services", and all three survived the move to one process without anyone re-reading them. The pattern
is worth more than any of the three fixes.

---

## Second amendment, 2026-08-09 (step 4, release-control's stack pass) — the broker rejection is re-argued on merit, and still holds

**The decision is untouched for a second consecutive pass.** This section exists because one of the
*rejected alternatives* above was rejected on a premise that no longer exists, and an inherited rejection
is not a decision.

The alternatives list says:

> "**A message broker or a pub/sub channel.** *Rejected by A-012 before it is rejected on merit*: the
> system must come up with one `docker-compose up` for a team with no dedicated ops. Adding a broker to
> save 30 seconds on an operation with a 5-minute target is the definition of a moving part that earns
> nothing."

**ADR-0028 put RabbitMQ in the stack during Stage 1.** The first sentence is dead; the second was never
tested, because the first ended the argument. This ADR's own author flagged the ordering — *"before it is
rejected on merit"* — which is why it was findable.

**Re-argued on merit, the answer is the same, and now it is a decision.** The concrete proposal is a
fanout exchange, a per-process exclusive auto-delete queue, and an eviction on release, restore and
withdrawal. Four objections, any two sufficient:

1. **It fires almost never.** Releases are human-rate — *"a handful per prompt per week"* in
   release-control's own load note — and withdrawal, the case where immediacy actually matters, is the
   rarest action in the product. This is ADR-0041's standing objection for the third time in three
   passes: *"the mechanism most likely to be wrong is the one exercised least — a path that only runs
   during an incident is a path nobody has watched work."* It deleted the spill file on that ground, and
   the amendment above deleted stale-if-error on it.
2. **It makes `app` a broker consumer for the first time.** Today `app` only publishes; every consumer
   lives in `worker`. A consumer, its connection, its recovery and its channel would sit inside the one
   process carrying a Success-metric latency budget — the process ADR-0046 and A-130 are both arguments
   for taking work *out* of.
3. **It does not close the window.** A restarted process, a consumer that has not yet bound, or A-130's
   gateway split each leave an entry to serve out. It converts *always within 30 s* into *usually
   instant, occasionally 30 s* — a weaker guarantee to state and a harder one to test.
4. **It contradicts four independent answers.** ADR-0012, ADR-0022, ADR-0038 and A-092 each arrived at
   TTL-or-nothing separately, in four different modules. Prope has four caches and invalidates none of
   them. Adding a fifth answer for the case with the largest headroom is the wrong place to break the
   pattern.

The failure mode of the shorter-TTL alternative was also re-checked and needs no revision: *"the
staleness is either acceptable or it is not; if it is not, the answer is a mechanism, not a smaller
number."*

**What changes as a result: nothing in the mechanism, and one sentence on two screens.** The release
screen already owed *"takes effect within 30 seconds"* (see the consequences above). ADR-0009's amendment
adds the same sentence to the withdraw confirmation, where the ADR title's word *"loudly"* had been
carrying an implication of *immediately* that this cache does not deliver.

**Pattern note, fourth consecutive pass.** The three cases above were adopted mechanisms resting on dead
premises. This one is a **rejected alternative** resting on a dead premise — which is the more dangerous
shape, because an adopted mechanism is at least read again when its module is touched, and a rejection is
read only by whoever is about to re-propose it.

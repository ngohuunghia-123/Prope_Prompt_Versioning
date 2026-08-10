# ADR-0001 — The released-revision pointer lives on the prompt property

**Status**: Accepted
**Date**: 2026-08-08
**Module**: prompt-registry (written while locking it)
**Related**: A-041, BR-03, BR-04, `00_context.md#success` (gateway p95 50 ms), ADR-0002

## Context

Two modules have a claim on "which revision is running right now". `release-control` produces the
decision; `prompt-registry` holds the revision it points at; `gateway` has to read it on every single
inbound request, inside a p95 50 ms budget that `00_context.md` records as the reason the whole
gateway design exists. Left undecided, the two modules form a dependency cycle — the shape that makes
parallel work collide and makes both modules untestable in isolation.

## Decision

`released_version_id` is a column on `prompt_property`, owned by `prompt-registry`. `release-control`
is the only caller permitted to change it, through one command,
`set_released_revision(prompt_id, version_id, release_id)`. The Approved-only rule (BR-03) is enforced
by a **database constraint**, not by application code in release-control: a write naming a revision
whose status is not `Approved` is rejected by the storage layer.

No module reads approval or release records to answer "what is running". Those records answer "how did
it get there", which is a different question with a different reader.

## Alternatives rejected

**Release-control owns the pointer; the gateway asks it.** Rejected on the hot path. The gateway would
resolve in two hops — ask release-control for the version ID, then ask the registry for the body and
binding — doubling the reads on the one path where latency was declared non-negotiable. It also makes
release-control, a low-traffic approval workflow, a hard runtime dependency of every production request
in every consuming product, which is a strange thing to page someone about at 3am.

**Derive the pointer by querying release records** (`latest release where prompt_id = X`). Rejected:
correct and slow, and it puts an ordering-and-tie-breaking rule on the hot path where a wrong answer is
"production served the wrong prompt text" rather than "a report looked odd". A denormalised pointer with
a constraint is cheaper to reason about than a query with an ordering invariant.

**Event-sourced projection of release events into a read model.** Rejected as disproportionate. A-012
fixes the ops ceiling at one `docker-compose up` with no broker; introducing a projection means
introducing lag, and lag here means the gateway serving a revision that was restored two seconds ago —
precisely the failure the ≤ 5 min restore metric exists to prevent.

**Enforce Approved-only in release-control's application code only.** Rejected. `00_context.md#success`
sets a target of **0** unapproved revisions reaching a release, and calls it the failure that makes the
product worthless. A target of zero does not survive being defended by one `if` statement in the module
most likely to be refactored.

## Consequences

- The gateway's resolution is one read, cacheable for 30 s (A-031), ~~invalidated by this write~~
  **expiring on its own**. *Corrected 2026-08-09 during release-control's stack pass* — ADR-0012 decided
  that nothing invalidates the resolution cache; a pointer write becomes visible within 30 seconds
  because the entry expires, not because this write reaches the gateway. Nothing reaches the gateway.
- ~~`release-control` writes a table it does not own.~~ **It issues a command; prompt-registry performs
  the write** (ADR-0008, superseding this line). `writes_tables_it_does_not_own` is `none` for every
  module in the build. The cross-module contract is real either way and is declared as an edge in
  `module_map.md`, not hidden — but the edge is a command, not a write, and ADR-0008 explains why that
  distinction is what keeps BR-03's constraint enforceable.
- Reversing this is a migration (a column moves, one command changes hands, the cache key changes),
  which is why it is an ADR and not only an assumption.

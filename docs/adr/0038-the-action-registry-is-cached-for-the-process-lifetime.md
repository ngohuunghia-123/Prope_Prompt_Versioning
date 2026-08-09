# ADR-0038 — The action registry is cached for the process lifetime, and nothing invalidates it

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: property-history
**Related**: A-025, A-054, A-120, A-124, ADR-0012, ADR-0022, ADR-0023, ADR-0024, ADR-0026, ADR-0028,
ADR-0031

## Context

`append()` validates every event twice against `history_action_registry`: the action name must be one of
the 31 registered (A-120, ADR-0024), and every key in the `details` payload must be allow-listed for
that action (A-124). Both checks run **inside the caller's open transaction** (ADR-0023), so their cost
is a share of release-control's approve-and-release, provider-access's rotation, and access-control's
grant rather than a cost of its own.

property-history's lock already assumed an answer without naming it. Its performance requirement reads:

> "p95 < 3 ms — one INSERT plus one registry lookup, **the registry held in process memory**"

This ADR makes that explicit, because the interesting property is not that a dict lookup is fast. It is
that **a miss does not degrade — it raises, fails the user's transaction, and pages someone.** The
module's own alert says so: `PropertyHistoryAppendRejected` is a page, and the lock notes it *"must stay
0 in a correct build — every increment is a caller bug that has just failed a user's transaction."* A
cache whose staleness is indistinguishable from a caller bug deserves its lifecycle written down rather
than inferred.

This is Prope's **fourth** caching decision, and the series is deliberate: ADR-0012 (the resolution cache
expires and nothing invalidates it), ADR-0022 (nothing in access-control is cached, so revocation lands
on the next request), A-025 (provider credentials, 60 seconds, in-memory only). ADR-0022 already counts
them. **The default in Prope is no cache**; each one is argued for individually, and a per-module Cache
row reads `n/a` unless it has an ADR.

## Decision

**Read `history_action_registry` into an immutable in-process mapping once at process start. No TTL, no
refresh, no invalidation path.** The mapping is the same in the `app` and `worker` containers (ADR-0028),
both of which import the library from the same image (ADR-0026).

The safety argument is a deploy ordering, not a data property. ADR-0031 runs migrations **before**
restarting the application. So for the only change that can occur — a migration seeding a new action —
the ordering is: the row exists, then the code that names it starts. **Adding an action is safe by
construction.**

The reverse direction, removing an action, is unsafe under this scheme: old code could name a row that
no longer exists between migration and restart. That is accepted rather than defended against, because
A-120 closes the vocabulary at 31 names — 30 until ADR-0054 added `user_tombstoned`, which is this
ADR's *"adding an action is safe by construction"* being exercised for the first time — and AC-6
asserts the registry and the five lock files are an
equality — a removal is already a coordinated, tested, multi-file change, and it is not a scenario the
cache makes worse than the migration already does.

The registry table is `SELECT`-only for `prope_app` (ADR-0025's reasoning applied to a second table for
a different reason: it is seeded configuration, not a log). There is no user-editable path and no API
that writes it, so there is no runtime event that could make the cache stale.

## Alternatives rejected

**Query the registry on every append.** Rejected on where the cost lands. It is one extra round trip
inside every caller's open transaction — two on approve-and-release, which writes two events in one
transaction (A-076) — spent on 30 rows of seeded configuration that cannot change while the process
runs. It buys correctness against a scenario that does not exist, and it charges for it on the path of
every state change in the product. Its one real advantage is that it needs no reasoning about deploy
ordering, which is a cost this ADR pays once in writing instead.

**A TTL cache, 60 seconds, the same shape as A-025's credential cache.** Rejected as a refresh path with
no reachable trigger. A-025's cache has a TTL because the underlying credential genuinely changes at
runtime — a workspace rotates a key and the change must land without a deploy. The registry changes only
by migration, and every migration is followed by a restart, so the refresh would fire every 60 seconds
for the process's whole life and never once find a difference. Copying a pattern because it exists in
the codebase is how a system acquires code whose purpose nobody can reconstruct.

## Consequences

- The `p95 < 3 ms` append target is now conditioned on something stated rather than assumed, and the
  condition is testable: a benchmark asserting `append()` issues exactly one statement.
- **A registry migration requires a restart to take effect**, which ADR-0031's deploy already performs.
  Someone applying a migration by hand against a running instance will not see the new action — that is
  a `PropertyHistoryAppendRejected` page with a confusing cause, and it is the one operational sharp
  edge this decision creates.
- The mapping is immutable after load. Not a stylistic preference: it is read on the hot path of every
  writing module's transaction from both the `app` and `worker` processes, and a mutable module-level
  dict is how a later "just refresh it here" turns into a race that fails a user's release.
- `registered_actions()` continues to read the table rather than the cache. It exists so a route-table
  test and a CI schema check can assert the vocabulary (AC-6), and a test that checks the cache against
  the lock files instead of the database would assert nothing about what `append()` will accept after
  the next migration.
- Prope's caching series now stands at four, each with a different rule: expire-only (ADR-0012), never
  (ADR-0022), 60-second TTL (A-025), and process-lifetime with no invalidation (here). Any fifth should
  say which of the four it is copying and why.

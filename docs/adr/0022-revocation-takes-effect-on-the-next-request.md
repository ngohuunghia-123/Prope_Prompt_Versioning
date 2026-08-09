# ADR-0022 — Nothing in access-control is cached: revocation takes effect on the next request

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-114)
**Module**: access-control (written while locking access-control)
**Related**: A-025, A-031, A-080, A-081, A-092, ADR-0012, ADR-0014, ADR-0021, OQ-006, OQ-012

## Context

Prope caches in two places already, and both were deliberate. The gateway holds a 30-second resolution
cache that **expires and is never invalidated**, because no invalidation mechanism exists in a system
with one-way edges and no broker (ADR-0012, A-080). Provider-access holds decrypted credentials for 60
seconds, so a rotation is effective within a minute (A-092).

Access-control sits on the same hot path and is asked the same question thousands of times with the
same answer, which makes it look like the third obvious place to cache. `authenticate_api_key` runs on
every gateway request; `may()` runs on every management request.

The reason to stop and think is what a stale answer means in each case. A stale released pointer serves
an *approved* revision one TTL late — the wrong revision, briefly, and every candidate for "wrong" here
has already passed human review. A stale permission answer serves a **revoked** credential. Those are
not the same kind of wrong, and revoking a leaked key is an incident response, where "within 30 seconds"
and "immediately" are materially different promises to make to somebody whose key is in a public repo.

The cache also buys much less here. Resolution returns a revision body, its provider binding, and its
fallback answer — a real join. Authentication is one primary-key read plus one hash (ADR-0021), and a
permission check is two indexed reads over small tables.

## Decision

**No authentication result, permission decision, key scope, role binding, or session is cached anywhere
in Prope. Every check reads current state, and a revocation is effective on the next request.**

- `authenticate_api_key`, `may_resolve`, `may`, and `visible_subject_filter` all read live.
- Sessions are **server-side rows**, not self-contained tokens, so signing a person out or removing them
  from a workspace takes effect at once rather than at expiry.
- Revoking a key, removing a member, or changing a role bindings takes effect on the next request, with
  no TTL to wait out and no cache to invalidate — because there is nothing to invalidate.
- Callers may not cache the answers either. This is stated as a contract term rather than assumed, since
  the tempting optimisation is on the caller's side of the seam and the gateway's own cache sets a local
  precedent for it.
- If a load test later shows the reads are actually the constraint, the fix in order of preference is a
  connection-level or statement-level database optimisation, then a cache with an explicit revocation
  epoch — never a plain TTL, which reintroduces exactly the window this decision removes.

## Alternatives rejected

**A 30-second TTL, matching the gateway's resolution cache.** Rejected on what staleness costs. The
resolution cache goes stale toward a previously approved revision; this one would go stale toward a
credential someone has deliberately killed. ADR-0012 accepted its window because no mechanism existed to
close it and the consequence was bounded; here a mechanism does exist — read the row — and the
consequence is not bounded, because a leaked key's blast radius is whatever the attacker does in the
window.

**Cache only the successful authentications, not the denials.** Rejected, and it is worth naming because
it sounds conservative. Successful authentications are precisely the ones a revocation is trying to stop.
Caching only the hits is caching only the cases that matter.

**Cache permission decisions but not authentication.** Rejected as a distinction that will not survive
contact with the code. Once one cache exists in this module, the next thing to be cached is whatever is
hot, and the reasoning that permitted the first will be quoted for the second. The absence is easier to
maintain than the boundary.

**A signed token carrying permissions, verified without a read.** Already rejected in ADR-0020 and
rejected again here for the same reason from the other direction: a token is a cache with no eviction.

**A cache with explicit invalidation on revoke.** Rejected as the thing the system has already proven it
cannot do. ADR-0012 established that Prope has no invalidation mechanism — one-way edges, no broker
(A-012) — and access-control is forbidden from calling the modules that would need telling. Writing an
invalidation path here would mean inventing the broker A-012 rules out, and the version that gets built
instead is a TTL wearing an invalidation's name.

**Follow provider-access's 60-second credential cache for consistency.** Rejected as a false analogy,
and it is the closest call of the five. That cache exists to avoid a KEK unwrap and a decrypt on every
dispatch — real cryptographic work — and what goes stale is a *rotation*, which is planned maintenance
rather than an incident. Here there is no expensive operation to avoid and what goes stale is a
revocation. Same shape, different stakes, opposite answer.

## Consequences

- Revocation is immediate and can be described that way in the product, which is the sentence someone
  needs to hear on the day a key ends up in a public repository.
- Access-control's read volume is the highest in the system: one authentication per gateway call plus
  one scope check, on top of every management request. That load is now stated in the performance table
  with numbers, and the first load test can contradict it. A module with no cache and no measured budget
  is how a 50 ms path quietly becomes an 80 ms one.
- The database is a hard dependency for every request in Prope, including the gateway's. That was
  already true through prompt-registry and is now true twice over. It is consistent with the accepted
  reversal in `00_context.md` — Prope is a hard dependency of its consumers' request paths — and it is
  another reason OQ-012's uptime target matters.
- Prope now holds three caching decisions that point in different directions: expire-only (ADR-0012),
  short-TTL (A-092), and none (here). They are not inconsistent; each was decided by what a stale answer
  costs. Anyone adding a fourth cache should be made to answer the same question.
- **Qualified 2026-08-09 by ADR-0044 and A-133.** This decision spent five rejected alternatives
  defending *"no TTL to wait out"*, and there turns out to be exactly one event that undoes it: a
  **restore**. ADR-0036's 24-hour RPO means a restore brings back every key, grant, binding and
  membership revoked inside the window — and the `history_event` rows recording those revocations roll
  back with them, so nothing inside Prope can reconstruct what was lost. ADR-0044 fixes the half that
  was cheap, excluding `access.session` from the dump so a restore signs everybody out rather than
  resurrecting sessions A-108 chose server-side rows specifically to be able to end. A-133 records the
  rest, with the procedural step and a revisit trigger on OQ-006's sign-off. The promise this ADR makes
  is therefore exact: revocation is immediate **in the running system**, and a restore is not the
  running system.
- **Unaffected by ADR-0042**, and worth stating because the two touch the same reads. The bootstrap
  functions read live rows on every request exactly as this decision requires; a revoked key's
  `revoked_at` comes back in the same tuple and the refusal is the application's, on the next request.
  They bypass the tenant policy, not the freshness.

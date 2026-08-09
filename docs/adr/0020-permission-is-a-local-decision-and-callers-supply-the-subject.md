# ADR-0020 — A permission decision is one local function call, and the caller supplies the subject's attributes

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-111, A-115, A-116, A-118)
**Module**: access-control (written while locking access-control)
**Related**: A-007, A-012, A-013, A-044, A-045, A-081, ADR-0003, ADR-0008, ADR-0018, OQ-006

## Context

Six modules depend on access-control, and every one of them describes the same call in the same words:
`may(actor, action, subject)`. Two of those callers sit on paths with hard budgets — the gateway's p95
of 50 ms, and prompt-registry's list and search endpoints, whose lock already states that "permission
filtering lives in the repository layer, not in handlers, so a new query path cannot forget it".

Writing the signature out reveals a problem the module map does not name. Deciding whether an actor may
edit a prompt needs three things: the actor's role bindings in the workspace, any per-prompt grant, and
**the prompt's own owner and access level**. The first two are access-control's tables. The third is
`prompt_property`, which belongs to prompt-registry — and `access-control → prompt-registry` is a
forbidden direction, because access-control is the oracle every feature module consults and an edge
back into one of them is a cycle.

The same asymmetry shows up on list endpoints. If `may()` is the only surface, a page of 50 prompts is
50 permission calls, and prompt-registry's repository-layer filter cannot be written at all — it would
need to join across module tables, which its own lock forbids in writing.

`00_context.md#scope` also puts a "configurable policy engine" out of scope, and A-012 caps the system
at one `docker-compose up` with no component that needs its own runbook.

## Decision

**A permission decision is a synchronous in-process function call over access-control's own tables,
and the caller passes the subject's authorisation-relevant attributes as parameters.**

```
may(actor, action, subject) -> allow | deny
  actor   = {user_id | key_id, workspace_id}
  action  = a value from a closed enumerated vocabulary (A-115)
  subject = {type, id, workspace_id, owner_id?, access_level?}
```

- The caller has already read the row it is about to act on, so `owner_id` and `access_level` are in
  hand. It passes them. Access-control supplies the role bindings, the grants, and the matrix. Neither
  side can answer alone, and the split falls exactly on who owns which table.
- **Effective permission is the union** of what the actor's role bindings grant and what a per-prompt
  grant grants. There are no negative grants and nothing subtracts — a rule that removes a permission
  someone else added is a rule whose outcome depends on evaluation order (A-111).
- The action vocabulary is **closed and default-deny**: an action not in the list is denied, so adding
  a feature cannot accidentally be permitted by falling through (A-115).
- A **set form** exists beside the singular one: `visible_subject_filter(actor, subject_type)` returns
  `all`, `none`, or an explicit id list, which a caller pushes into its own SQL. That is what makes
  prompt-registry's repository-layer filter implementable without a cross-module join (A-118).
- A refusal is **not-found when the actor cannot see the subject** and **forbidden naming the
  permission when they can see it but may not act on it** (A-116). This reconciles A-045's blanket
  not-found rule, which is scoped to visibility, with release-control's lock, which already promises
  refusals that name the missing permission.
- No policy language, no external policy service, no rules DSL. The matrix is a table of
  `(role, action)` rows, so OQ-006's eventual answer is data rather than code.

## Alternatives rejected

**Access-control looks the subject up itself.** The obvious design, and it is the one that cannot be
built. Resolving a prompt's owner means reading `prompt_property`, which requires
`access-control → prompt-registry` — a forbidden edge, and worse, a cycle, because prompt-registry
already calls access-control on every endpoint. The alternative form of this — access-control keeping
its own copy of every subject's owner and access level, synchronised somehow — is two writers on one
fact with no broker to synchronise them (A-012), which is the same failure the map broke three times
already.

**Pass only ids and let access-control ask the caller back.** A callback inverts the cycle without
removing it, and it would put an unbounded call chain on the gateway's 50 ms path. Rejected on both
counts.

**One boolean per row on list endpoints — just call `may()` fifty times.** Rejected. It is correct and
it is also how the 30-second find target dies: fifty in-process calls is survivable, fifty calls that
each read the grant table is not, and the version of this that gets written under deadline pressure is
the one that skips the filter for "internal" queries. The set form exists so the fast path and the
correct path are the same path.

**A policy engine — OPA, Casbin, a rules DSL.** Rejected against two explicit constraints:
`00_context.md#scope` lists a configurable policy engine as out of scope, and A-012 forbids any
component that needs its own runbook. It would also make the permission matrix unreadable at exactly the
moment OQ-006 is answered and someone has to check that the written matrix matches the running one.

**Carry permissions in a signed token so no lookup is needed on the hot path.** Rejected because it
trades away revocation, which is the property that matters most here — see ADR-0022. A token is a
cached decision with no way to invalidate it, and the whole point of the consumer-key surface is that a
leaked key can be killed.

**Deny-overrides — let a grant or a role explicitly remove a permission.** Rejected. Negative grants
make the answer depend on the order rules are evaluated in, and the first support question is always
"why can't this person do this", which under union has one answer and under deny-overrides has a
search. Nothing in the source documents asks for it; BR-01's private-by-default is a *starting* state,
not a subtraction rule.

## Consequences

- Access-control depends only on property-history, and its dependency list stays that way by
  construction rather than by discipline — the signature makes the forbidden edge unnecessary rather
  than merely forbidden.
- The caller supplies `owner_id`. A caller that lies gets the answer it asked for. This is honest rather
  than mitigated: in a single process (A-012) a caller that would forge an owner id is a caller that
  could have skipped the check, so the boundary being defended here is module hygiene, not a hostile
  one. If the modules are ever split across processes, this signature is the first thing that must
  change, and that is written here so it is not rediscovered.
- `prompt_grant.prompt_id` is a **value, not a foreign key** — an FK would point access-control's schema
  at prompt-registry's table, in the forbidden direction. This is the mirror of the case in
  provider-access, where the FK ran the same way the dependency did and was therefore free (A-096); here
  it runs against it and is not. Prompts are never deleted (ADR-0002), so the constraint would buy
  nothing anyway.
- The `(role, action)` matrix is a seeded table. OQ-006's answer becomes rows, which is the difference
  between a migration and an afternoon.
- Every module's "fails closed" promise now means one specific thing: `may()` raising is treated as
  deny, and no caller has a code path where an error becomes an allow.

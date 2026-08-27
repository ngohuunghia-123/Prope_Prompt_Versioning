# ADR-0069 — A route is frozen at create, and the deadline is the whole request

**Status**: Accepted
**Date**: 2026-08-27
**Decision**: user (scope, snapshot semantics, and the advancing rule were each put and each answered)
**Module**: prompt-registry (three tables, two revision columns, five routes) / gateway (the loop, the
budget, four metrics, two alerts) / provider-access (the delete refusal widens) / evaluation,
prompt-readiness (entry 1, explicitly)
**Amends**: ADR-0013 — *"no retry"* survives verbatim and acquires a scope, **per entry**
**Replaces**: A-084. **Leaves intact**: A-088, A-091, A-164, A-024, ADR-0012, ADR-0035, ADR-0045, ADR-0053
**Widens**: A-096 / INT-016 — the provider-delete refusal now also names a template
**Related**: A-022, A-023, A-024, A-031, A-034, A-035, A-043, A-046, A-053, A-084, A-085, A-088,
A-089, A-115, A-130, A-143, A-164, ADR-0009, ADR-0012, ADR-0013, ADR-0030, ADR-0054, OQ-012, OQ-140

## Context

A revision binds exactly one provider configuration and exactly one upstream model, and the gateway
makes exactly one upstream attempt. When that provider rate-limits, rejects the credential or falls
over, the only cover Prope has is the revision's static `fallback_answer` — canned text, no model
involved — and the only *recovery* is a new revision plus a review.

That second sentence is the problem. Minutes at best, and it is a governance action being used as
incident response. The approval gate exists so that no prompt reaches production without a person
having read it; using that same gate as the switch that restores service teaches people to approve
under pressure, which is the one habit the product cannot afford. Meanwhile most workspaces already
hold credentials for more than one provider, sitting idle while the released prompt serves canned text.

So: a workspace defines a named, ordered list of `(provider, model)` entries — a **router combo** — a
revision binds one instead of a single pair, and the gateway walks the list.

Three questions had to be answered before a line of it could be written, and the answers are what this
ADR records. The awkward one is the third: **ADR-0013 already decided that the gateway does not retry**,
and A-084 says so in as many words, on two grounds — a retry doubles the worst case inside the
strictest latency budget in the system, and it multiplies load against a provider that is by hypothesis
already failing.

Both objections are *answered* here rather than waived. That distinction is the spine of clause 4.

## Decision

### 1. A revision binds one pair or one route, never both, and the engine says so

Three new tables in the `registry` schema — `router_combo`, `router_combo_entry`, and the frozen
`revision_route_entry` — plus two columns on `revision`: `route_combo_id` and `route_combo_name`.

Four states, the fourth refused by PostgreSQL and not by a code path:

| `provider_config_id` | `route_combo_id` | entries | meaning |
|---|---|---|---|
| set | NULL | 0 | today's single pair |
| NULL | set | 1..5 | routed |
| NULL | NULL | 0 | an unbound draft, as today |
| set | set | — | **refused** by `ck_revision_binds_a_pair_or_a_route_never_both` |

`ck_revision_binding_is_whole` — the constraint that already refuses half a pair — is **kept verbatim**.
A routed revision has both pair columns NULL, so `(NULL IS NULL) = (NULL IS NULL)` holds and the
constraint still means exactly what it always meant. Its name appears in the schemas, in `TrialRequest`,
in the lock file and in tests; changing what a constraint *says* while keeping its *name* is how a
constraint quietly stops meaning what everybody thinks it means.

**An entry cannot exist without its marker**, and that too is the engine's job. `revision_route_entry`
carries a NOT NULL `route_combo_id` and a composite foreign key to `revision (version_id, route_combo_id)`
— which is BR-03's own trick reused. `fk_prompt_property_released_version_id` references
`revision (version_id, status)` so that only an `Approved` revision can be released; the same shape
here means an orphan entry, or an entry on a pair-bound revision, is refused rather than validated.

The inverse — a routed marker with zero entries — is caught by a rowcount on the copy (clause 2) and
deliberately **not** by a deferred constraint trigger. `create_revision` writes inside a savepoint and
retries on `uq_revision_prompt_id`; a `DEFERRABLE INITIALLY DEFERRED` constraint fires at COMMIT,
*outside* that savepoint, and would poison the whole request transaction instead of one attempt.

**The route is a child table and not a JSONB column on the revision**, for one discovered reason that
outweighs the rest. `DELETE /api/v1/providers/{id}` is refused *only* by an `IntegrityError` from
`fk_revision_provider_config_id` — `count_revisions_binding_provider` exists and has zero callers
(OQ-140). A JSONB route has no foreign key and there is no legal way to add one back: provider-access
reading `registry.revision` violates the cross-schema rule, and provider-access asking prompt-registry
is the forbidden reverse edge. The refusal would simply stop working for routed revisions, and it would
stop working silently. A child table gets it back for free, along with ordering, uniqueness and RLS
that `test_tenant_coverage` sees on day one.

### 2. A route is a **snapshot**, taken at create. The combo is a template

Choosing a combo copies its entries onto the revision, frozen, in the same `INSERT ... SELECT` that
cannot see a torn read because it performs no read:

```sql
INSERT INTO registry.revision_route_entry (version_id, workspace_id, route_combo_id, priority,
                                           provider_config_id, upstream_model)
SELECT :version_id, :workspace_id, e.combo_id, e.priority, e.provider_config_id, e.upstream_model
FROM registry.router_combo_entry AS e WHERE e.combo_id = :router_combo_id ORDER BY e.priority
```

Editing the template afterwards changes **nothing already released**. A prompt adopts the edit only
through a new revision and a new approval. Deleting the template leaves every revision made from it
working, which is why `route_combo_id` on the revision is a value and carries no foreign key —
ADR-0054's rule for `actor_id`, applied to a second thing that must outlive its referent.
`route_combo_name` is snapshotted beside it so a review screen still reads correctly after a rename.

**The strongest argument for this is not A-024. It is ADR-0012's cache.** The gateway's resolution
cache has a 30 s TTL and *nothing invalidates it* — a second broker queue for invalidation was proposed
twice and rejected twice on merit. A live combo reference would make an edit in a Settings dialog a
production change that the cache cannot see and cannot be told about: the same prompt would route two
ways depending on which process answered, for a window nobody chose. Under a snapshot, the cached value
is immutable by privilege — `revision_route_entry` holds `SELECT, INSERT` and never `UPDATE` or
`DELETE` — so a stale cache entry is not merely tolerable, it is *correct*.

A-024 is then satisfied rather than strained: provider and model remain part of the revision, the
approval record still describes what can run, and A-024's own `revisit_when` — *"a team wants to swap
models without a review cycle"* — has not been triggered, because nothing here swaps a model without
one. Routing widens what a reviewer approves from one pair to an ordered set of them.

**There is deliberately no `route` field on the create request.** The client names a template and the
server copies it. Accepting a client-constructed list would mean "which combo was this" is a claim
rather than a fact, and a caller could compose a route no combo in Settings ever contained.

### 3. The gateway advances. provider-access still attempts exactly once

The loop lives in `gateway/routes.py`. `dispatch()` is untouched and still issues exactly one upstream
request per call, so **A-088 holds literally** — it puts retry policy at the caller, and the gateway
*is* A-088's caller. `attempt` is still always 1 in provider-access's logs; upstream call volume and
dispatch count are still the same number.

Which failures advance is derived from the closed classification table rather than listed by hand, so
a new `ErrorClass` cannot arrive silently unclassified:

```python
ADVANCING = frozenset(k for k, v in CLASSIFICATION.items() if v.fallback_eligible)
ADVANCING_CONFIGURATION = frozenset({ErrorClass.CONFIGURATION_UNUSABLE, ErrorClass.BLOCKED_ADDRESS})
```

`fallback_eligible` already means *"this failure is about the provider, not about the request"*, which
is precisely what *"should somebody else try it"* asks. It yields exactly seven: `rate_limited`,
`credential_rejected`, `model_unavailable`, `upstream_unavailable`, `upstream_timeout`,
`contract_violation`, `admission_refused`. `content_policy` and `invalid_request` are excluded, and
excluding `content_policy` is not an oversight — advancing on it would be policy-shopping, a request
one provider refused being walked to a provider that will not.

**`CONFIGURATION_UNUSABLE` advances but is not fallback-eligible, and those are two different
questions that one flag has been answering.** `dispatch._prepare` raises it when a configuration is
missing, **disabled**, or unverified. "An admin disabled provider A this morning" is the single most
likely reason an entry is unusable and is the exact scenario a combo exists for; not advancing means a
Settings toggle takes production down while entry 2 sits healthy. But `fallback_eligible=False` is
right and stays: ADR-0013's rule is that a Prope-side misconfiguration must not be papered over with
canned text, and that reasoning is about the canned answer, not about the next provider. So the loop
reads `_advances()` and the fallback still reads `error.fallback_eligible`. If every entry is
misconfigured, the caller gets today's 500 and never a fallback. `BLOCKED_ADDRESS` joins for the same
reason. `KEY_UNAVAILABLE` does not: no KEK in this process means every entry fails identically, and
advancing would only burn the budget.

### 4. `DEADLINE_MS` is the budget for the **whole request**, not for one attempt

This is the clause that answers ADR-0013 instead of waiving it.

```python
DEADLINE_MS = 60_000        # the budget for the WHOLE request
MIN_ATTEMPT_MS = 5_000      # below this, a further attempt is theatre
```

Each dispatch receives what is *left*. The worst case is 60 s whether a revision binds one pair or
five, so *"a retry doubles the worst case"* is answered by construction rather than by argument, and
OQ-012's eventual latency number lands on one budget rather than on a number multiplied by an entry
count. Under `MIN_ATTEMPT_MS` the loop stops and answers with the last real error, because an attempt
that cannot finish produces a timeout that says nothing about why the route failed.

*"It multiplies load against a provider that is already failing"* does not apply at all: a route goes
to a **different** provider. Nothing is ever re-sent to the one that just failed — which is why
ADR-0013 is amended and not superseded. Prope still never sends the same request to the same provider
twice; "no retry" now carries the scope it always implicitly had, **per entry**.

Admission is the quiet win. `admit(key.key_id)` wraps the whole of `_serve`, so a routed request holds
exactly **one** slot against A-143's per-key cap however many entries it walks, while provider-access's
own per-configuration admission is entered and released per dispatch against a *different* pool each
time. An `admission_refused` therefore advances into cross-provider load shedding, which is arguably
the best single thing this feature buys and nobody asked for it.

### 5. Failover ends at the first byte, in exactly the same place the fallback does

A streaming dispatch returns a lazy relay: a pre-first-byte failure only becomes visible when the first
item is pulled. The loop pulls it, which is what puts the streaming failover boundary on the same seam
ADR-0013 drew for the fallback — and the abandoned relay is `aclose()`d before the next entry asks its
own pool for a slot, or concurrency leaks under precisely the conditions failover fires.

Mid-stream stays `Outcome.TRUNCATED`: never a fallback, and now never a second provider either.
ADR-0013's hybrid-response argument applies verbatim and harder here. Splicing provider B's
continuation onto provider A's half-answer produces something that looks like one model's output and
is two, and no reader of that call record could ever tell.

### 6. The order of last resorts, and it ends with the **last** error

Every entry in priority order → the revision's canned `fallback_answer`, if the **last** error is
fallback-eligible → otherwise that last error, translated.

The last and not the first. The caller must be told what the last thing Prope tried did, and
`retry-after` on a 429 is only meaningful from the final attempt. A `retry-after` harvested from entry
1 and returned after entry 3 answered is a number about a provider the caller never reached.

No new `Outcome` member and no schema change for traceability. `CallFacts.provider_config_id` and
`upstream_model` are overwritten per attempt, so the call record already names the entry that actually
served — or, on exhaustion, the last one tried. A failed-over caller received a real model answer, so
the outcome is `ok`; a `failed_over` member would break `ck_call_record_outcome_values` and silently
change every `outcome=ok` share on every dashboard ever drawn. `error_class` is **not** set on a
successful failover: an `error_class` on an `ok` row reads as an error nobody had.

Which *position* served is carried on the response — `x-prope-route-entry`, `x-prope-route-attempts`,
and three keys in the `prope` body block that are always present so the shape is stable.

## Consequences

**A workspace can be silently running on its backup, and this is the hazard the feature creates.**
Every call returns 200, the answer is real model output, latency is the only outward sign, and a
primary provider can stay down for weeks with nobody looking. `GatewayRouteBackupServing` — the
`entry != "1"` share over 15 minutes — is the mitigation and **ships with the feature rather than
after it**. It is a ticket and not a page, because the product is working; what is broken is somebody's
primary provider.

**A rejected credential now advances like any other provider failure**, so a botched key rotation is
invisible from the caller's side. `prope_provider_credential_rejected_total{provider_config_id}` already
exists in provider-access and has no alert. It needs one, and that gap is stated here rather than
discovered later.

**p99 for a routed prompt rises toward the full deadline during an outage.** A caller who would have
received a 429 in 200 ms now waits for entry 2, and possibly entry 3. That is the trade the feature
*is*, and it is bounded by clause 4 rather than open-ended. `GatewayRouteBudgetExhausted` fires when
the bound actually binds, because a route whose later entries are never reached is decoration.

**`GatewayFallbackRateHigh` changes meaning without changing its expression.** On a routed revision a
canned answer is served only after *every* provider on the route has failed. It has moved from "an
upstream is failing" to "a workspace has no working provider at all" — a rarer and much worse event,
and it still pages.

**Evaluation, readiness and the playground trial read entry 1 only, deterministically.** A-164 is
unchanged and explicit: *"a probe wants the truth about what this binding does"*, and a silent failover
would measure a model the released revision may not use. A cost delta computed against whichever
provider happened to be up is not comparable across runs, which is the whole point of a fixed suite.
This is not free — all three previously passed `revision.provider_config_id` straight into `dispatch`,
which is NULL for a routed revision, so all three read the primary entry now or a combo-bound prompt is
un-evaluable. Readiness's `revision_has_no_binding` rule widens for the same reason, or every
combo-bound revision collects a false finding on a card whose entire premise (ADR-0067) is that it
measures rather than opines.

**Deleting a provider a template names is refused, not cascaded.** A cascade can take a two-entry combo
to one, producing a combo the UI's own validation would refuse to save — a state reachable only by
deletion, which a customer finds before a test does. A-096 / INT-016's refusal sentence widens from
"a revision" to "a revision or a router combo". Disabling remains available and is the escape hatch.

**Five is the cardinality bound**, enforced by `CHECK (priority BETWEEN 1 AND 5)` against a
`(combo_id, priority)` primary key — so the cap needs no count column and no trigger, and it bounds the
`entry` metric label at five series under ADR-0030. Raising it is a one-line migration.

**Permissions did not grow.** Five `ManagementAction` members map onto the existing
`PROVIDER_CONFIGURE` and `CATALOGUE_READ`, so `Action` stays closed at 27 and A-115 is untouched. The
honest cost: an admin who may configure providers may now also define routing. Same authority, wider
surface.

**No property-history event for template CRUD, deliberately.** Under snapshot semantics, editing a
template changes nothing in production, and the thing that *does* reach production already emits
`revision_created` carrying the frozen entries. A gap, and a stated one.

**Per-entry generation parameters are out of scope.** `parameters` remains one object on the revision
(A-024). It is the obvious next ask and it is not answered here.

## Alternatives rejected

**A live combo reference.** Rejected on ADR-0012's cache before it was rejected on A-024: an edit in a
Settings dialog would become a production change that a TTL-only cache cannot see, for a window nobody
chose, and the same prompt would route two ways depending on which process answered.

**A JSONB `route` column on the revision.** Rejected on the provider-delete refusal, which it destroys
unrecoverably (clause 1), and on the four things it would move from the engine into application code.

**Retrying the same entry.** ADR-0013 and A-084 are right about this and it stays refused. What changed
is only that the *next* entry is a different provider.

**Advancing on `content_policy`.** Policy-shopping. A request one provider refused on policy grounds
should not be walked to a provider that will accept it, and a product whose failover does that is
selling a compliance hole.

**Resuming a dead stream on another provider.** One answer from two models, indistinguishable from one
in the record. Clause 5.

**A `failed_over` outcome member.** Breaks `ck_call_record_outcome_values` and silently re-bases every
`outcome=ok` share ever drawn, to record something the served `provider_config_id` already says.

**A combo as a first-class model name** — callers referencing the combo instead of the prompt. Violates
A-023 and puts routing outside the review gate entirely, which is the one thing this ADR is organised
to prevent.

**Per-entry configured deadlines.** A second knob on a budget that already has one, and the first
support question it generates is why the sum exceeds the request deadline.

**Failover inside evaluation and readiness.** A-164, and a measurement that silently changes what it
measured is not a measurement.

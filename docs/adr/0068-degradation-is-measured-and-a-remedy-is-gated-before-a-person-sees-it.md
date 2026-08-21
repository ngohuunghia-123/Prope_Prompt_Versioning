# ADR-0068 — Degradation is measured from metadata, and a remedy is gated by machine before a person sees it

**Status**: Accepted
**Date**: 2026-08-20
**Decision**: user
**Module**: prompt-improvement (new, the fourteenth lock) / prompt-registry (a second ADR-0055 reader,
this one windowed) / property-history (a **sixth** `writing_module`)
**Supersedes**: nothing. **Leaves intact**: ADR-0018, ADR-0028, ADR-0035, ADR-0045, ADR-0053, ADR-0055
**Related**: A-016, A-020, A-029, A-102, A-115, A-116, A-124, A-145, A-162, A-163,
ADR-0019, ADR-0025, ADR-0051, ADR-0054, ADR-0055, ADR-0057, ADR-0064, ADR-0066, ADR-0067,
OQ-006, OQ-154, OQ-157, OQ-158, INT-043 … INT-050

## Context

`prompt-readiness` (ADR-0067) answers *is this ready?* before a release. Nothing answers the question
after one. Deck 6 opens on exactly that gap — *"latency doubled, cost tripled, and one answer in twenty
is fabricated. When do you find out? When a user complains, which is the worst and most expensive way."*

A model does not crash when it degrades. It returns `200 OK` and gets quietly worse, and every signal
that it is doing so is already sitting in `ledger.call_record`: truncation, fallback, caller errors, the
output-to-input token ratio, the latency tail, the share of traffic that has pinned away from the
released revision. Prope is on the request path, so it has this data and nobody else does.

The temptation, and the thing every competitor ships, is to feed all of it to a model and let the model
propose a rewrite. That is the commodity feature `positioning.md` §261 refuses to lead with, and here it
is worse than commodity — it is **actively hostile to non-negotiable #1**. A queue of unvalidated
model-authored edits, each carrying a confident self-narrated rationale, converts *no prompt reaches
production without a recorded human approval* into a stream of fast, low-information approvals. The
approval survives as a database row and stops being a decision.

Two constraints therefore shape the whole module, and the second is the load-bearing one.

## Decision

### 1. The evidence is metadata arithmetic. The module reads no body, ever.

Eleven detectors, each a pure function over one window of `ledger.call_record` metadata compared with
the window before it. No model is involved in deciding whether an anomaly is real. `outcome=fallback`
rising **is** a fact; the model is never asked to agree.

The read is ADR-0055's and not a new one: per prompt, behind `prompt.read`, through **prompt-registry's**
seam. A direct edge from this module to `call_ledger` would be the flat cross-prompt reader ADR-0055
rejected by name, and it would disclose that private prompts exist through a door nobody classified as a
read (BR-01). `ledger.call_body` is untouched, unsampled and unasked for — an earlier draft of this
design proposed consented sampling into an observation-shaped store, and the scheduled re-probe replaced
it entirely, which is why there is no second store of customer content to defend.

The ban holds in the **write** direction too, and that one had to be built rather than merely declared.
The gate spends the workspace's provider credit, so somebody must check the spend ceiling — and
`check_spend_ceiling` lives in `call_ledger.seams`. It is called inside `evaluation`'s gate runner, next
to the dispatches it guards, exactly as `prompt_readiness.probe` calls it inside its own runner. A
ceiling enforced by whichever caller remembered to ask has as many implementations as it has callers,
and the one that forgets is the unattended nightly job. The result is that this module holds no
`call_ledger` import at all, in either direction, which is the form the ban is actually testable in.

One detector reads nothing from the ledger. **PROFILE_DRIFT** compares the property's current Usage
Profile with the copy stamped on the released revision at submit: *serving the public; approved as
internal*. It is the payoff of ADR-0067's stamping decision and is undetectable without it.

### 2. A candidate edit clears the prompt's own eval suite before any person sees it.

This is the decision the module exists around.

A candidate that regresses is **discarded, counted on `prope_improvement_gate_rejected_total`, and never
rendered**. Not shown-with-a-warning, not shown-greyed-out: never rendered. A person's attention is the
scarcest control in this product, and spending it on a suggestion the machine could already tell was bad
is how the control wears out.

**No suite means no edit proposal, for every remedy family, under every anomaly.** The precondition is
absolute rather than a strong default, because the gate is the one machine-side check standing between a
model's output and a human's approval, and without a suite there is nothing for it to be. The remedy in
that case degrades to a **case** proposal — *these are the cases that would make a future edit gateable
at all* — which is the one shape that turns the precondition into something a person can act on rather
than a dead end.

**The honest limit, stated here rather than discovered later.** *"Did not regress on this suite"* is
exactly as strong as the suite. The published 26/30 → 9/30 collapse happened on a dimension the authors
had not thought to measure, which is the failure mode by definition. The gate is a floor and not a
proof, and §3 exists because a bounded edit is far easier to keep inside what a suite covers than an
unbounded one.

### 3. Remedies come from a closed anomaly→family catalogue. Free-form rewriting does not exist.

```
probe leaked            -> tighten the refusal block
truncation rising       -> add an explicit length rule
output:input drifting   -> add a brevity clause
profile drift           -> (note only — a declaration is a person's to change)
```

Every family is a bounded, parser-derived transform over canonical XML: it may add or replace one block
and must round-trip with an **identical declared-variable set**. A remedy that silently dropped a
`{{variable}}` would break every call site the moment it was released, and a catalogue is what makes
that assertable rather than hoped for.

The model's job is narrow and stated in full: it **ranks** anomaly clusters, **picks** a family from the
set the anomaly already makes reachable, and **writes one evidence sentence in `vi`**. It does not
decide whether an anomaly is real, which families are reachable, whether the suite exists, whether the
gate passed, whether the rate cap admits the proposal, or whether anything is written at all.

### 4. What reaches a person is an evidence card, never a self-narrated rationale.

*What changed, in consequence language. The eval delta, per case. The token and cost delta. Which
consumer keys call this.* And explicitly **not** the model's story about why its own edit works.

The reasoning is narrow and it is not a general distrust of explanations: the causal story an optimiser
attaches to its own edit does not describe the edit's behaviour. Showing that story to a reviewer asks
them to trust an unreliable narrative *and* an unvalidated judgement at once, which is the precise setup
that produces rubber stamps.

**And the queue is rate-capped by the database.** At most one open proposal per prompt, enforced by a
partial unique index rather than by a service check — because a control in application code is a control
somebody refactors away, and *"break down large batches"* is worthless if the batch can be a hundred.

### 5. Delivery is pull-only. This module adds no egress path, and that is not negotiable.

It holds private data (every prompt in the workspace, plus its traffic shape) and untrusted content
(those same bodies). Two legs of the lethal trifecta are irreducibly present, so the third must be
**structurally absent** — deck 5 slide 41.

Prope sends no email today: there is no SMTP anywhere in `src/` or `deploy/`, and even invitations are
deliberately a row and a string somebody reads out (ADR-0057). Deck 6 prescribes Slack alerting and
**this module declines it**, because adding an outbound channel to the widest-reading agent in the
product completes the one configuration the same deck says not to build. The inbox is a screen somebody
opens.

### 6. Tier 3 is a declared non-goal, not deferred scope. OQ-154 does not block this module.

OQ-154 names this module by name — *"blocks the improvement-agent module entirely"* — and it is right
about the data. Tool errors and retrieval failures have nowhere in Prope to live, so *"the retrieval
returned nothing and the model filled the gap"* is the most compelling sentence in the brief and this
module cannot say it.

That is **declared out of scope** rather than left as a half-blocked lock. A lock whose scope is
half-blocked is a lock nobody trusts, and `build_order.md` cannot represent one. If OQ-154 answers in
favour of storage, that is an amendment to this ADR with a date and a reason.

### 7. Two meters, and they must never be added together.

Scheduled probes and gate runs spend the **workspace's** money on its own credential and appear as
`ledger.call_record` rows with `source='probe'`. Triage spends **Prope's** money on the app-owned model
and must never be a `call_record` and never enter a cost delta — the rule
`prope_evaluation_drafter_cost_usd_total` already carries, for the reason it carries it: a delta compares
what two revisions cost to *serve*, and a convenience feature's bill inside that number would make a
revision look more expensive because somebody enabled a schedule.

## Consequences

**A sixth `writing_module`, and the line ADR-0067 declined to cross is crossed deliberately here.**
ADR-0067 kept readiness dismissals in `readiness.dismissal` on A-102's precedent: a dismissed lint is not
a state change on a prompt property. That reasoning holds and is not being reversed. A **proposal
disposition is a different object**: it is a person's decision about a machine-authored change to a
prompt currently serving production traffic, and *who decided what the machine proposed* is exactly the
accountability record ADR-0025's append-only privilege model exists for. Three actions are seeded —
`improvement_proposal_accepted`, `improvement_proposal_dismissed`, `improvement_proposal_expired` — and
`ck_history_action_registry_writing_module_values` learns `prompt-improvement`.

**`gate_failed` is deliberately NOT among them**, and the draft spec is corrected here. A candidate that
fails the gate never becomes a proposal, so there is no disposition to record; it is a counter and
nothing else. Writing a machine's rejection of a machine's suggestion into the accountability record of a
prompt that never changed would dilute the record with events no person took.

**Accepting a proposal writes no revision.** The route marks the disposition and hands back the candidate
body; the write is prompt-registry's `create_revision` on a separate, explicit request under
`revision.create` — chat-orchestrator's `pending_action` shape and ADR-0066's rule. So the route is
declared under `revision.create` too: handing somebody a body destined for a revision they could not
create would be a permission gap wearing a read's clothes.

**The first sweep on a workspace emits one summary row and not two hundred findings.** A-162's inversion,
reused: two hundred items on the first screen anybody sees is deck 6 slide 64 arriving fully formed, and
an inbox nobody can face is an inbox nobody opens again. `improvement.sweep.is_first_sweep` makes that a
property of the data rather than of a code path somebody can regress — **and it is why `sweep` rows are
retained indefinitely.** A retention term on that table would let a dormant workspace's rows expire and
silently make it a first-time workspace again, which is a bug that reports itself as a friendly summary.

**Zero anomalies writes nothing and says nothing.** An empty inbox is the success condition, exactly as
ADR-0064 inverted prompt-observation's.

**A daily sweep is a fifth and sixth resident of `worker`**, joined by hand in `prope.worker` (D-13),
enumerating workspaces through `access.list_workspaces()` and reading each one under its own policy —
ADR-0051's shape rule, and its reason: an unscoped query under ADR-0045 returns **zero rows** and a sweep
built on one would run cleanly, find nothing, and look healthy.

**`prope_improvement_gate_rejected_total` is the module's own smoke alarm.** If it reads zero for a
month, the gate is not working — either nothing is being proposed, or everything proposed is passing, and
the second is not credible. That deserves an alert about the module rather than about a prompt.

**No new action is minted.** The five routes reuse `prompt.read`, `prompt.edit`, `revision.create` and
`spend_ceiling.manage`; the schedule route takes the last of those because enabling a recurring charge
against the workspace's provider credential is a spending decision before it is an authoring one. The
vocabulary stays at twenty-seven and `ck_role_permission_action_values` is untouched.

## Alternatives rejected

**Show unvalidated proposals with a warning label.** The warning is read once. This is the rubber stamp
with a disclaimer attached, and the disclaimer is what makes it feel safe.

**Let the model rewrite freely and rely on the suite to catch mistakes.** The suite is a floor, and an
unbounded rewrite is precisely how you reach a dimension nobody measured. §3 bounds the edit so the floor
is more likely to be load-bearing.

**Sample `call_body` with the workspace's consent.** This was the first draft's answer and it is gone.
The scheduled re-probe measures the same degradation against cases Prope already ships, so there is no
second store of customer content and no consent flow to get wrong. ADR-0018 stands untouched.

**Alert to Slack when a finding opens.** Refused at §5. It is the third leg of the trifecta, added to the
one component in the product that reads every prompt in the workspace.

**Let release-control consult the evidence card.** Refused in both directions. A card a release read
would be a gate, and the entire argument for this design is that the gate is a person. `prompt-readiness`
D-03 applies here with more force, not less: a post-publish finding has even less standing to gate a
future decision than a pre-publish one.

**One `finding` table shared with `readiness`.** Same shape, different lifecycles — a readiness finding
is recomputed from a body on every card read and frozen at submit; an improvement finding is durable,
dedupes on `(prompt, rule_id)` and accrues an occurrence count. Merging them needs a discriminator column
and two retention policies in one table, which is two tables with extra steps. Two tables is the safer
default until somebody argues otherwise.

# ADR-0067 — Readiness is a measurement, not an opinion, and it knows what the prompt is for

**Status**: Accepted
**Date**: 2026-08-20
**Decision**: user
**Module**: prompt-readiness (new, the thirteenth lock) / prompt-registry (the Usage Profile column) /
call-ledger (a fifth `source`) / access-control (a twenty-seventh action)
**Supersedes**: nothing. **Leaves intact**: ADR-0018, ADR-0035, ADR-0045, ADR-0053, ADR-0055
**Related**: A-011, A-016, A-021, A-029, A-062, A-078, A-099, A-102, A-115, A-145, A-163, A-164,
ADR-0019, ADR-0020, ADR-0027, ADR-0053, ADR-0054, ADR-0061, ADR-0066, OQ-006, OQ-157,
INT-037, INT-038, INT-039, INT-040, INT-041, INT-042

## Context

Prope registers a prompt, versions it, evaluates it and gates its release on a human approval. What it
never says is whether the thing about to be approved is *fit for the job it claims to do*. A diff shows
what changed. An eval suite shows whether the cases somebody wrote still pass. Neither answers the
question a reviewer actually has in front of a fresh import: **is there anything wrong with this that
nobody has thought to test for?**

Every competitor answers it with a lint. Loop, PromptLayer and Bedrock all ship "an AI agent that
proposes prompt improvements", and `positioning.md` §261 and `BRIEF.md` §202 both refuse to lead the
pitch with that phrase for a reason worth restating: **a context-free lint is right often enough to be
installed and wrong often enough to be ignored.** It tells a prompt that runs on synthetic fixtures
behind an internal dashboard that it lacks a guardrail against public misuse. The person dismisses it,
and the next finding — the one that mattered — is dismissed with the same reflex.

There are two separable problems in that sentence, and the module is the answer to both.

## Decision

### 1. The check knows what the prompt is for. The Usage Profile is declared, never inferred.

Four axes, each lifted from the course material rather than invented, stored on
`registry.prompt_property` and copied onto the revision:

```
audience         internal | authenticated_user | public
untrusted_input  none | user_text | retrieved | third_party
acts             answers_only | emits_tool_calls | irreversible
sensitivity      synthetic | business | personal_data
```

A rule states which profiles admit it, and a finding the profile does not admit is dropped **after**
generation, so the drop is countable. An internal-only prompt is never told it lacks a public-facing
guardrail, and that is not a heuristic — it is a declaration the person made.

**Declared, never inferred (A-163).** A model guessing that a prompt is customer-facing and then
lecturing about it is precisely the false positive this module exists to avoid; inference here would be
the bug and not the feature. The cost is a field somebody has to fill in, and the answer to an empty
one is a **conservative default plus a badge**: undeclared reads as `public / third_party / irreversible
/ personal_data`, rendered as *undeclared — assuming worst case*. A conservative default is corrected
once, in one dropdown, and permanently silences a class of finding. A guess has to be argued with every
time.

**Stamped onto the revision** (ADR-0019's pattern — a figure keeps the price row that explains it).
A profile that existed only on the mutable property would silently re-scope every past finding and
every past approval the moment somebody flipped `internal` to `public`; a profile that existed only on
the revision would make "we launched publicly" require a new revision with an unchanged body. Both, so
the reviewer approves a body *and* the exposure it was judged under, and the drift between the two is
detectable rather than silent.

**Legs 1–3 of the lethal trifecta become computable** from that declaration: private data
(`sensitivity`) plus untrusted content (`untrusted_input`) plus external comms (`acts`). A prompt
declaring all three raises the one finding that outranks everything else on the card, and it is the only
finding printed in full even when it was dismissed last time.

### 2. The finding is a measurement. A shipped adversarial catalogue leads; the model augments.

The card does not say *"this prompt looks easy to inject"*. It says **"3 of 12 known injection cases
were not refused"**, because the twelve cases are `builtin:chong-tiem-prompt@1` — files in the image,
identical in every workspace, versioned with the product, scored by the same deterministic
`forbidden_phrase` / `regex` assertions a hand-written suite uses.

That dodges the entire question of whether the agent's opinion is trustworthy. A test passes or it
fails. It also makes the number **comparable**: a shipped set is a benchmark, and an agent-drafted set
is incomparable to anything, including to itself last week (deck 7 slide 13's golden-dataset
discipline, on a mechanism `evaluation` already ships).

The model gets three jobs and no fourth: it drafts prompt-specific cases when somebody asks, it decides
which member of a **closed** rule catalogue fires for the small set of findings no test can express, and
it writes one evidence sentence. It never decides the yardstick, never scores quality, and never
rewrites a body.

### 3. A probe is not an eval run.

Lane C dispatches real calls against the candidate revision on the workspace's credential. It writes
**no** `evaluation.eval_run` row, creates no suite, attaches nothing, and enters no cost delta. Its
results live in `readiness.probe_run` and `readiness.probe_case_result`, in this module's own schema.

`evaluation`'s rule is *a model does not decide what a prompt is measured against*, and the cheap way to
build Lane C — write an `eval_run` and reuse the runner — breaks it in the one place it is load-bearing.
A probe measures readiness; a suite measures a release. Keeping them apart costs a fifth
`ledger.call_record.source` (`probe`), minted for the reason the fourth was.

### 4. Nothing blocks. There is no `blocker` severity and the schema must not carry one.

Two reasons, the second sharper.

`evaluation` runs real assertions against real dispatches and is **warn-only** (A-016). A module whose
findings are partly model-chosen cannot defensibly be a stronger gate than the one that runs real tests.

And blocking on a **self-declared** profile creates an incentive to misdeclare it. A gate that corrupts
its own input is worse than no gate, and that input is what every other rule in the module reads.

The severity CHECK admits exactly `advice` and `warning`. A third value that did nothing would be an
argument for making it do something, filled in later by whoever is in a hurry.

## Consequences

**release-control is a forbidden dependency in both directions**, and that has a concrete cost the lock
pays rather than dodges. The natural design freezes the reviewer's copy of the card at submit — but a
submit hook is an edge, and an edge is decision 4 defeated by composition. So the freeze happens on the
**card read**: the first `GET .../readiness` on a revision that has left `Draft` writes
`readiness.report` once, idempotent under a unique constraint. Release-control does not know this module
exists. For the same reason, a probe is started explicitly rather than riding along with the suites
A-062 runs at submit.

**A twenty-seventh permission, `probe.start`, and nothing is reused.** `run.start` describes a probe
accurately — *may spend workspace money dispatching against a revision* — and reusing it would cost no
vocabulary at all. It is refused because A-115's set is mapped to roles by `role_permission` rows: reuse
means every role already holding `run.start` gains probe capability on the deploy that ships this, with
nobody deciding. A minted action starts ungranted, and is seeded to Admin and Owner.

**No history events, and property-history is not a dependency.** A dismissal is recorded in
`readiness.dismissal` with its actor and reason, on prompt-observation's precedent (A-102): a dismissed
finding is not a state change on a prompt property. The one profile event is written by prompt-registry
against registry's own column.

**One narrow i18n exemption.** ADR-0053 stands — the client renders the `code`, not the `message`, and a
CI check fails the build on a rule with no `vi` key. The exception is one generated evidence line per
finding, and it carries two obligations: it is generated **directly in Vietnamese** (a translation step
would be a second model call on the display path), and it passes its output rail **before storage**, not
before render, because a rail applied at render is a rail somebody bypasses with a different client.

**The module's normal operating input is other people's prompt bodies, one of which may be an
attacker's.** It therefore holds private data and untrusted content irreducibly, which means the third
leg of the trifecta must be **structurally absent**: no tool in this module sends, posts, fetches or
emails, asserted by a test over the catalogue rather than by review.

**The honest metric is the dismissal rate per `rule_id`.** A rule dismissed 80% of the time is a rule to
retire, not to tune — deck 6's alert-fatigue prescription applied to findings instead of pages. OQ-157
owns the threshold and the decider; that retirement is a routine act with a written threshold rather than
a debate is settled here.

## Alternatives rejected

**A column on `prompt_property` holding a lint result.** Cheapest by far, and it fails on the first
requirement: dismissals must persist across revisions and the reviewer's copy must be immutable. Those
are two tables with different lifetimes, not a column.

**Reusing `evaluation` for the probe.** Rejected above — it is the one reuse that costs a rule the
product treats as non-negotiable.

**Letting the agent propose body rewrites pre-publish.** Rejected, and the reason is evidential rather
than aesthetic. Pre-publish there is no baseline; on a fresh import there is usually no suite either, so
an author who accepts a rewrite and *then* writes cases writes them against the edited body — the before
was never measured. That is the 26/30 → 9/30 regression, invisible by construction. Only remedies with a
definition of correct that does not require running the prompt — relocating an interpolation out of an
instruction block — may carry an edit. Semantic remedies belong to `prompt-improvement`, behind a
baseline and an eval gate.

**A `blocker` severity, defaulting to off.** Rejected in decision 4.

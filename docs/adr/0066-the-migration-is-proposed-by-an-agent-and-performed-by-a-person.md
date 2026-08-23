# ADR-0066 — The migration is proposed by an agent and performed by a person

**Status**: Accepted
**Date**: 2026-08-19
**Decision**: user ("write a Agent Skill for them to self integrate (scan and upload all prompt to
prope, track relationship, etc), or our team will integrate for customer")
**Module**: a new deliverable, `skills/prope-migrate` — runs in the **customer's** repository, in the
customer's own coding agent. Prope ships the instructions, not the agent
**Supersedes**: nothing. **Amends**: nothing
**Related**: A-011, A-020, A-021, A-078, A-154, A-161, A-162, ADR-0060, ADR-0063, ADR-0064, ADR-0065,
OQ-006, OQ-013, OQ-155, OQ-156, BR-01

## Context

ADR-0063 concludes that the refactor was never the thing to avoid — it was the thing to automate. That
conclusion rests on an observation about where the customer already is: **a coding agent is already in
their repository.** It has read access to every file, every branch, and every rarely-taken path, which
is more than a proxy watching production traffic will ever have.

The asymmetry is large enough to be the whole argument:

| | observation (ADR-0059, now ADR-0064's audit) | an agent reading the repository |
|---|---|---|
| a prompt behind a branch that did not run | invisible | found |
| variable names | inferred by diffing renders — `{{var_1}}`, `{{var_2}}` (A-154) | the real identifiers, from the source |
| a prompt assembled from three concatenated strings | seen only as the rendered result | seen as the assembly |
| what calls what | not visible | the call graph is in the file |
| **rewriting the call site** | impossible | **a diff a person reviews** |

But an agent with write access to a codebase and upload access to a registry is also the most dangerous
tool in this document, and for a reason that has nothing to do with code quality: **A-020**. *No real
corporate prompts in the pilot until OQ-006 and OQ-013 are answered.* A scanner whose default is to find
prompts and upload them is, precisely and immediately, the thing A-020 forbids.

## Decision

**The skill produces a reviewable proposal. A person performs every act that changes anything.**

Four phases, and the boundary between the second and the third is where the whole safety argument
lives.

### 1. Scan — read only

The agent reads the repository and identifies candidate prompts: string literals reaching an LLM client,
template files, prompt constants, and the assembly sites where several are concatenated. It writes
nothing outside its own output directory and touches no network.

### 2. Manifest — a file a person reads

The output is a single reviewable artefact listing, per candidate: the source location, the extracted
body in the canonical form prompt-registry already accepts (A-011, A-078), the variables with their
**real names** from the source, the proposed `namespace/name`, and the call sites that would change.

The manifest is the deliverable of a skill run. **Nothing has been uploaded, and nothing in the
repository has changed.** A run that ends here is a complete, successful run — this is the dry-run
default, and it is dry-run by default because A-020 is a policy and defaults are how a policy survives
contact with a hurry.

### 3. Register — a person, holding a session, having read the manifest

Upload happens only on an explicit second act, against a workspace the person names, using their own
session. It creates prompts and revisions through prompt-registry's own routes — the same routes the web
application uses, subject to the same permissions.

**It does not approve and it does not release.** The revisions land as `Draft`. Non-negotiable #1 is not
weakened by the migration path, and the reason is sharper here than anywhere else: a bulk import that
auto-approved would put forty unreviewed prompts into production in one command, with one recorded
actor, which is precisely the outcome the entire approval chain exists to prevent. The person who
approves them approves them one at a time, in the web application, seeing the diff and the eval result —
and if that is tedious for forty prompts, the tedium is the control working.

### 4. Rewrite — a diff, in the customer's version control

The agent replaces each literal with a gateway call through the SDK (ADR-0065) and leaves the result as
uncommitted changes or a pull request. It never commits, never pushes, and never runs a deploy. A human
reviewer reads a diff in the tool they already use, and the migration enters the codebase the way every
other change does.

### 5. Verify — the audit closes the loop

After the rewrite ships, ADR-0064's observing key answers the question the scan cannot answer about
itself: **what did we miss?** Prompts assembled at runtime, loaded from a database, or living in a
service nobody pointed the scan at will forward and appear as findings. The migration is complete when
that punch list is empty, not when the scan reports success.

This is why ADR-0064 refused to delete the machinery. The scan and the audit have exactly complementary
blind spots.

### 6. `namespace/name` is proposed, never assumed

A-021 makes a model name immutable and ADR-0061 makes the namespace the access container, so a prompt
filed in the wrong folder is filed there for life — A-049 makes retirement terminal, so there is not even
a clean remedy. This is the same trap ADR-0060 refused to walk into with `AdoptionProposal.namespace`,
and it is refused again here for the same reason: **the skill proposes a name and a namespace, and the
manifest review is where a person chooses them.** A default that is right 90% of the time is a
permanent mistake in the other 10%.

### 7. Relationships come from runtime, not from static analysis

The ask included *"track relationship"*. v1 does not.

A call graph across dynamic dispatch, configuration-driven routing, and async queues is genuinely hard to
recover statically, and a **wrong** chain is worse than no chain: it draws a graph somebody trusts. Once
the SDK is in place the chain is threaded correctly by construction (ADR-0065 §2) and observed rather
than inferred.

So the skill reports call sites and their enclosing functions as *context for the reviewer*, and does not
attempt to emit a conversation graph. **OQ-155** carries whether static hints are worth adding later.

## Alternatives rejected

**Upload by default, with a `--dry-run` flag to opt out.** The conventional CLI shape. Rejected on
A-020: the flag that protects a policy has to be the one you must type to *bypass* it, not the one you
must remember to type to honour it.

**Have the skill approve and release what it registers.** What "self integrate" could be read to mean,
and it would make a migration one command. Rejected: it converts the migration into a bulk unreviewed
release and makes non-negotiable #1 a setting. If a workspace wants forty prompts live today, forty
approvals is the price, and break-glass already exists for the genuine emergency — declared, counted,
and with a 24-hour follow-up.

**Ship a static analyser as a Prope-hosted service the customer uploads their repository to.** Removes
the dependency on the customer having an agent. Rejected as a much larger trust ask than the one
ADR-0063 just rejected — source code is a bigger disclosure than production traffic — and as a product
Prope would then have to maintain per language.

**Write the skill for one specific agent.** Rejected as needless coupling: the instructions are prose and
a manifest schema, and any competent coding agent can follow them. Where a host-specific packaging
format helps distribution, that is packaging, not design.

**Let the skill read the ADR corpus to decide naming conventions.** Attractive — Prope's own docs are
right there. Rejected because the skill runs in the *customer's* repository against the *customer's*
conventions, and importing Prope's internal vocabulary into somebody else's namespace choices is how a
migration produces forty prompts named the way Prope would have named them.

## Consequences

- **A-020 gets a default rather than a reminder.** Dry-run-by-default is the first place the pilot policy
  is enforced by a mechanism instead of by a sentence in a document. It should be read as the model for
  how OQ-006 and OQ-013 get honoured elsewhere.
- **The manifest is a new artefact containing real prompt bodies, sitting in the customer's repository.**
  It must be git-ignored by default and it must say so loudly — a migration that leaks prompts into
  version control has moved the problem rather than solved it. **OQ-156** carries whether the manifest
  should be encrypted at rest on the customer's disk.
- **Prope's own team performing white-glove integrations is bounded by one rule**, from ADR-0063: every
  manual integration ends with a rule added to this skill. A migration performed by hand that teaches the
  skill nothing has been performed twice.
- **Registered-but-unapproved becomes a common state**, in bulk, for the first time. The web
  application's prompt list has to make a forty-`Draft` workspace navigable — filtering by status stops
  being a convenience and becomes the primary view during a migration.
- **The skill will be wrong sometimes, and the manifest is where that is survivable.** A false positive
  is a row a reviewer deletes; a false negative is caught by ADR-0064's audit. Neither failure reaches
  production, which is the property the phase boundary was chosen to give.
- **This is not a moat and should not be mistaken for one.** Anyone can write a scanner. What is
  defensible is the destination — the approval gate, the immutable revision chain, the traceability —
  and the skill's job is to get customers to it, not to be it.

# ADR-0064 — Observation is a migration audit, not an adoption path

**Status**: Accepted
**Date**: 2026-08-19
**Decision**: agent, under ADR-0063 ("optimize or discard my previous solution for unable to solve
problem")
**Module**: prompt-observation (the reading changes, the module does not) / gateway (the forwarding
mode, unchanged) / access-control (the per-key switch, unchanged)
**Supersedes**: nothing. **Amends**: ADR-0059's stated purpose, ADR-0060's framing of the inbox as an
adoption queue
**Related**: A-020, A-154, A-162, ADR-0059, ADR-0060, ADR-0061, ADR-0062, ADR-0063, ADR-0066, OQ-147,
OQ-151, SR-2

## Context

ADR-0063 finds that an observation delivers none of the four non-negotiables and that the observe path
asks more of a customer than any comparable product's on-ramp. The obvious next move is to delete it —
four ADRs, a module, ten migrations' worth of tables, and a set of passing tests.

**That would be the wrong reading, and this ADR exists to stop it.**

The machinery is not wrong; the *claim made about it* was wrong. ADR-0059 said observation was how a
customer adopts Prope. It is not. But there is a different question, which nothing else in Prope can
answer, and which becomes urgent the moment ADR-0066's migration skill exists:

> The agent scanned the repository and registered forty prompts. **Did it find them all?**

A static scan cannot answer that about itself. It missed what it missed. Prompts assembled at runtime,
built by string concatenation across three functions, loaded from a database, or living in a service the
scan was never pointed at — every one of those is invisible to the reader and obvious to the gateway
the first time it runs.

An observing key pointed at a **migrated** application answers it directly: **anything still forwarding
is a prompt the migration did not find.** That is a completeness proof, it is empirical rather than
inferential, and it is worth more than the adoption story it replaces.

## Decision

**Nothing is deleted. The inbox changes what it means, and gains a lifecycle position.**

### 1. Every table, constraint, policy and test survives unchanged

`observation.observation`, `observation.sighting`, the fingerprint and variable-inference rules (A-154),
`ck_api_key_observe_is_all_or_nothing`, the fourth `source` value `observed`, ADR-0062's
namespace-shaped entry rule, ADR-0061's folder privacy, and
`tests/integration/test_gateway_observes_a_legacy_app.py` — all of it stays, byte for byte. This ADR
writes no migration.

The reason is not sentiment. Every one of those pieces is *exactly* what an audit needs: it groups by
fingerprint so a hundred calls of one missed prompt are one finding rather than a hundred; it masks
timestamps so a missed prompt does not report as a new finding every midnight; it keeps findings private
to a folder so an audit of a customer's production traffic is not workspace-readable by default.

**The audit was the better fit all along.** ADR-0060's grouping rules were written to make an inventory
usable; they make a *punch list* usable for the same reasons and with none of the read-only problem,
because a punch list is supposed to be read-only.

### 2. The inbox is a punch list, and an empty inbox is the success condition

This is the inversion, and it is the whole ADR in one line.

Under ADR-0059, **rows in the inbox were the product working** — every observation was a prompt Prope
had discovered, and more was better. Under ADR-0063, **rows in the inbox are work outstanding**, and
the state a migrated workspace is driving toward is **zero open observations**.

Which means the two dispositions already built (ADR-0060) keep their names and swap their weight:

- **adopt** — *"this is a real prompt the migration missed; register it properly."* Formerly the happy
  path, now the corrective one.
- **dismiss** — *"this is not a prompt we govern"* — a health check, an internal eval, a third-party
  library's own call. Formerly the exception, now a legitimate and common resolution.

Nothing in the schema changes. `adopted_at` and `dismissed_at` are still the two facts and
`ObservationStatus` is still derived from them.

### 3. Observation is scoped to a window, not left on

A key that observes forever is a proxy the customer never agreed to keep. ADR-0063's whole objection is
that standing in front of production traffic is a large ask; that objection does not disappear because
the purpose changed.

So the intended shape is **temporary by convention**: enable observation on a key, run the migrated
application through a representative period, read the punch list, resolve it, turn observation off. The
switch already supports this exactly — ADR-0061's `PUT .../scope` takes effect on the very next request
with no TTL to wait out, and A-152 already made enabling it a deliberate, separately-audited act.

**Convention rather than a mechanism**, deliberately. An expiry column would be a scheduler, a sweep,
and a new failure mode where observation silently stops mid-audit; and A-012's *debuggable by one
person* clause is not spent on a timer that a person turning a switch off does better. Whether that
holds is **OQ-151**'s neighbour and is recorded there.

### 4. What the audit does **not** become

It does not become a *source* of prompts to register in bulk. Adoption stays exactly as ADR-0060 built
it: one group at a time, through prompt-registry's own create routes, ending in a revision somebody
approved. An "adopt all" button would recreate the read-only room at a different address — forty
prompts in Prope that nobody wrote, nobody reviewed, and nobody can vouch for.

## Alternatives rejected

**Delete `prompt-observation` and the forwarding mode.** The literal reading of *"discard my previous
solution"*, and it is the tidier repository. Rejected because the audit question is real, has no other
answer, and the code that answers it already exists and passes its tests. Deleting working, tested
machinery to make a strategy reversal look decisive is a cost with no benefit.

**Keep observation as an adoption path *and* an audit, and let workspaces choose.** Rejected on the
grounds that made ADR-0063 necessary: the adoption reading is what produced four failed configuration
attempts and a UI that had to be patched three times to explain itself. A mechanism with two stated
purposes will be adopted for the easier one. Naming one purpose is the decision.

**Make the audit a separate module.** It would duplicate fingerprinting, grouping and variable
inference — the three things hardest to get right and most expensive to have two of. Rejected for the
module map's standing reason: two implementations of *is this the same prompt* is exactly the drift the
architecture avoids elsewhere.

**Automatic reconciliation: mark an observation resolved when a registered prompt matches it.** Tempting
and wrong. A fingerprint match between an observed body and a registered body is evidence, not proof —
the registered prompt may be a different prompt that happens to open identically, and A-154's masking
makes false matches more likely rather than less. Auto-resolving would close punch-list items nobody
looked at, which is the one thing a punch list must never do. It is a proposal worth reconsidering as a
*suggestion* on the row rather than an action, and is carried in **OQ-151**.

## Consequences

- **The inbox UI is now the migration console**, and it is still unbuilt — seven routes with no screen.
  Its priority rises rather than falls: an audit whose only reader is `python seed.py --observations`
  is an audit nobody runs. It ships with ADR-0066's skill, not after it.
- **Empty is good, and the empty state must say so.** A screen that reads *"no observations yet"* is
  correct under ADR-0059 and actively misleading under this ADR, where it means *"the migration looks
  complete."* The two readings differ by whether observation was ever switched on for this workspace,
  which the key row already knows.
- **`seed.py --observations`'s diagnostic checklist inverts.** It currently explains why an empty
  result might mean *the observe path is misconfigured*. Under the audit reading, empty is the goal and
  the checklist is only relevant while confirming the audit is actually running.
- **SR-2 stays closed.** ADR-0061 gave observations a container and ADR-0062 wired it to the key; the
  demotion changes nothing about who may read a finding. An audit of production traffic is if anything
  more sensitive than an inventory, so the folder-private default is load-bearing here too.
- **A-020's line moves but does not move much.** An audit still files real corporate prompt bodies into
  Prope. The pilot constraint applies to the audit exactly as it applied to the inventory, and ADR-0066
  inherits it.
- **`playgrounds/chatbot-app/index.html` keeps its job with a new name.** It is no longer "the app
  before adoption, being adopted" — it is "an app the migration has not been run against", which is the
  same traffic and a different story. Its README leads with that.

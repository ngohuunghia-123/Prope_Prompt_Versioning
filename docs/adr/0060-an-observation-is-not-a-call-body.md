# ADR-0060 — An observation is not a call body, and it gets a module rather than a column

**Status**: Accepted
**Date**: 2026-08-18
**Decision**: user
**Module**: prompt-observation (new, the twelfth lock) / call-ledger (a fourth `source`) / gateway (the writer)
**Supersedes**: nothing. **Leaves intact**: ADR-0018, ADR-0028, ADR-0039, ADR-0041
**Related**: A-014, A-037, A-055, A-098, A-099, A-102, A-105, ADR-0018, ADR-0019, ADR-0025, ADR-0028,
ADR-0030, ADR-0039, ADR-0041, ADR-0045, ADR-0055, ADR-0059, OQ-013, OQ-147, OQ-148, INT-034, INT-035

## Context

ADR-0059 decides that the gateway forwards a call it cannot resolve. This decision is about the thing
that call leaves behind, and the obvious home for it is wrong three times over.

**`ledger.call_body` cannot hold it.** The whole point of an observation is that somebody reads it —
the inventory screen, the diff between Tuesday's body and Thursday's, the proposal a person adopts.
`call_body` is the one table in Prope with **no reader by construction**: ADR-0018 makes that a
decision, `ADR-0039` excludes it from the backup, and the retention job deletes it. ADR-0055 already
drew the line precisely, and it is the line this lands on the wrong side of: *metadata has readers,
bodies do not.*

**`ledger.call_record` cannot hold it either**, for a reason the schema states out loud:

```sql
CONSTRAINT ck_call_record_gateway_calls_carry_version_id
    CHECK (source <> 'gateway' OR version_id IS NOT NULL)
```

An observed call has no `version_id`, because no revision served it. `record_call()` enforces the same
rule one layer up and **drops the record entirely** when `version_id` is NULL. Relaxing that constraint
is not an option: it *is* the *"100% of gateway calls record a version ID"* success metric, and a
metric whose denominator has been widened to admit the failures is not a metric.

**And call-ledger cannot own the reader.** The map's forbidden edge is *call-ledger → anything*; with
no edge to access-control it can check no permission, which is exactly the reasoning ADR-0018 and
ADR-0055 both follow. An inventory screen needs a permission check.

## Decision

**One observed call writes two rows in two modules, and neither is a body.**

### 1. `ledger.call_record` gains a fourth `source`, exactly as revision 0020 added the third

```sql
ALTER TABLE ledger.call_record
    DROP CONSTRAINT ck_call_record_source_values,
    ADD CONSTRAINT ck_call_record_source_values
        CHECK (source IN ('gateway', 'eval', 'playground', 'observed')),
    ADD CONSTRAINT ck_call_record_observed_calls_name_no_revision
        CHECK (
            source <> 'observed'
            OR (
                prompt_id IS NULL
                AND version_id IS NULL
                AND revision_number IS NULL
                AND run_id IS NULL
                AND case_id IS NULL
                AND consumer_key_id IS NOT NULL
                AND pinned = false
                AND fallback = false
            )
        );
```

Revision 0020's argument for `playground` transfers whole and inverts cleanly. There, a third caller
needed its own value because recording it as `gateway` would corrupt the version-id metric's
*denominator* with traffic no consumer made. Here a fourth caller needs its own value because
recording it as `gateway` would corrupt the same metric's *numerator* with traffic no revision served.
Same metric, opposite end, same answer.

`ck_call_record_observed_calls_name_no_revision` is the mirror image of
`ck_call_record_playground_calls_are_internal`, and each clause is load-bearing in the same way:
`version_id IS NULL` because there was no revision and the row must not imply one; `consumer_key_id
IS NOT NULL` because a real key authenticated this and observation is never an internal caller;
`pinned = false AND fallback = false` because both are properties of a revision that does not exist.

**A-098's one-table-one-price-path property survives, and it is the reason this is worth doing.** An
observed call lands in the same spend total as everything else, which is what makes *"you are spending
this much on prompts Prope does not manage"* a number the product can put on a screen on day one,
computed by the pricing path that already exists.

### 2. `prompt-observation` is a new module and owns the body

A twelfth lock file, `S`, one bounded context, one outbound dependency.

| | |
|---|---|
| owns | `observation.observation` (one row per distinct body, per workspace), `observation.sighting` (per-call occurrences, rolled up) |
| deps_out | **access-control only**, hard |
| deps_in | gateway (write, off the response path), web SPA (read and adopt) |
| writes elsewhere | nothing |

**It writes no revision and creates no prompt.** The adopt action returns a *proposed* canonical body
and its inferred variable slots; the human posts it through prompt-registry's own create routes, and
prompt-registry writes the `property_created` / `revision_created` events it always writes. This is
prompt-conversion's shape exactly — *"conversion never saves a revision; the author reviews and may
edit before a separate save"* — and it is what keeps non-negotiable #1 airtight without a single new
check: an observation cannot become a released prompt by any path that does not run through a person
creating one and another approving it.

**It needs no edge to property-history**, and that is A-102's precedent applied rather than an
oversight. A-014 makes every state change on a prompt property an event; an observation is not a prompt
property. Dismissing one is recorded the way call-ledger records its own configuration changes — a
`dismissed_by` / `dismissed_at` / `adopted_prompt_id` column on the row itself. The moment an
observation *becomes* a prompt, the registry's own events take over and the trail is unbroken.

### 3. The write is direct, off the response path, and best-effort

The observation is written in the same post-flush `BackgroundTask` that already hands the call record
to call-ledger, in one transaction under the workspace's RLS. **No second queue.** ADR-0028 declares
one queue and its DLQ, and a second one has been proposed and rejected twice on merit; this is not the
third time.

The durability requirements genuinely differ, which is why the mechanisms may. A lost call record
loses money: it moves a workspace's spend total and every later cost delta, which is why ADR-0041
gives it a broker and A-099 gives it an idempotent upsert. A lost observation loses **one occurrence of
a fingerprint that has already been seen, and will be seen again on the next request**. The inventory
is a rollup over a stream; dropping a sample from a stream costs a counter, not a fact. It is counted
(`observation_write_failed_total`) and abandoned, exactly as A-037 abandons a body.

## Alternatives rejected

**Store the observed body in `ledger.call_body` and read it from there.** The cheapest thing that could
work, and it costs the most. It reopens ADR-0018 — the one table in the system with no reader — for a
feature that has nothing to do with why bodies are stored. It also fails on its own terms: `call_body`
is excluded from the backup (ADR-0039) and deleted by the retention job, so the inventory would silently
empty itself, and the first person to notice would be a customer whose discovery screen went blank.

**Relax `ck_call_record_gateway_calls_carry_version_id` to allow a NULL.** One line, no new module.
Rejected: that constraint is the written form of a success metric, and `call-ledger.lock.yml` calls it
*"a database constraint here, not a hope"*. Widening it to admit the rows it was written to exclude is
the failure mode this project has declined eight times.

**Put the observation tables in `registry` and let prompt-registry own them.** Defensible — adoption
ends there anyway, and the module already owns bodies. Rejected on the vocabulary test the module map
decomposes by. The registry's language is *property, revision, version ID, owner, access level*; every
one of those is a thing an observation does not have, and BR-01's private-by-default rule is a rule
about owners. An unowned, unregistered, unapproved body sitting in `registry.revision`-adjacent tables
would be the first row in that schema that no non-negotiable applies to. It is also the module already
scored `Small: no` — the one `L` in the build.

**Make it a table in the gateway's schema.** The gateway owns no durable data, deliberately, and that
is the sentence that keeps a 50 ms path honest. Rejected without much argument.

**Roll up on read instead of on write** — store raw sightings only and group at query time. Simpler
writer. Rejected because the grouping key is the expensive part (see A-154) and recomputing it across
every sighting on every screen load makes the discovery inbox slower the more valuable it gets.

## Consequences

- **`Source` gains a fourth member in `prope.call_ledger.domain`**, byte-identical to the CHECK set, and
  `records.record_call()`'s `version_id IS NULL` early return grows an exception for it — that guard is
  currently the reason an observed call would silently vanish.
- **The module map gains a ninth row and a ninth bounded context**, and this ADR is where the map's
  header is corrected: it still says *"eight modules across eight bounded contexts"* while
  `docs/modules/` has held eleven lock files since prompt-conversion, prompt-search and chat-orchestrator
  landed. The drift is recorded rather than quietly fixed.
- **`test_no_body_read_path.py` gets a second thing to assert.** It currently proves no route, callable
  or type can return a `call_body` column. It must go on proving exactly that, and it must not be
  weakened by the existence of a module that legitimately returns prompt text — so the new module's
  types are named in the test as *not* the thing being excluded, rather than the test being scoped down.
- **The retention question moves and gets sharper.** OQ-013's one remaining build-affecting half is *PII
  and redaction before storage*, and it was previously a question about a surface nobody was building.
  An observation is stored prompt text, read by people, kept until adopted or dismissed. That is now the
  most sensitive readable data in the system, and it is raised as OQ-148.
- **The backup rule needs a decision this ADR does not make.** ADR-0039 excludes `call_body` and
  ADR-0044 excludes sessions; `observation` is neither transient nor disposable — an inventory a customer
  spent two weeks accumulating is exactly the thing they would expect to survive a restore. It is
  included in the ADR-0036 dump by default, which is the rule for every table that does not declare
  otherwise, and OQ-148 is where a redaction answer could change that.

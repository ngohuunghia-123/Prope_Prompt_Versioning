# ADR-0024 — One event schema, a closed 30-name vocabulary, and a registered payload

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-119, A-120, A-122, A-124, A-125)
**Module**: property-history (written while locking property-history)
**Related**: A-003, A-014, A-044, A-045, A-046, A-076, A-096, ADR-0002, ADR-0018, ADR-0023, ADR-0025, NFR-02

## Context

A-044 fixed one writer, one table, one schema, and named six fields: actor, action, target type, target
ID, timestamp, reason. Locking the other seven modules produced the actual list of what will be written —
**30 event types from five modules**:

| Module | Events |
|---|---|
| prompt-registry | `property_created`, `revision_created`, `owner_changed`, `access_level_changed`, `retired` |
| release-control | `revision_submitted`, `revision_approved`, `revision_changes_requested`, `revision_released`, `revision_restored`, `revision_break_glass_released`, `release_withdrawn`, `review_task_closed` |
| evaluation | `eval_suite_updated`, `eval_run_started`, `eval_run_completed`, `eval_run_interrupted` |
| provider-access | `provider_configured`, `provider_updated`, `provider_disabled`, `credential_rotated` |
| access-control | `workspace_created`, `member_added`, `member_removed`, `role_assigned`, `role_revoked`, `access_granted`, `access_revoked`, `api_key_created`, `api_key_revoked` |

Laying them side by side surfaced four things the six fields do not cover.

**The six fields lose facts the product needs.** `revision_released` without `previous_version_id` cannot
answer "what did we go back from"; `role_assigned` without the role is an event that records that
something changed. A payload is forced.

**A free-form payload is where a prompt body leaks.** It would be the only column in Prope with no
declared shape, written by five modules, and A-046's rule — bodies, fallback answers, credentials, and
`prope.variables` values never appear in a log line, a metric label, or a history event — has no
enforcement point without one.

**The Activity view spans four modules.** "Everything that happened to this prompt" pulls events whose
targets are a property, a revision, a release, a suite, and a grant — tables owned by four modules, none
of which this one may join to (A-122, and it depends on nothing by A-044).

**Two events in one transaction have one timestamp.** Approve-and-release is a single request writing two
rows (A-076). Ordered by timestamp, the release trail shows them in an arbitrary order.

## Decision

**One row shape, a closed vocabulary registered in this module, and a payload whose keys are declared
per action.**

```
history_event
  seq              bigserial, monotonic — the ONLY sort key (A-125)
  id               ULID, prefix hev_ (A-045)
  workspace_id     value, not an FK
  actor_type       user | system
  actor_id         value, not an FK — nullable only for actor_type = system
  action           one of 31 registered names, <target_type>_<past participle> (A-120)
  target_type      closed enumeration
  target_id        value, no FK (A-122)
  scope_prompt_id  nullable — the owning prompt, stamped at append (A-119)
  reason           nullable text, ≤ 500 chars — user-authored, never a body
  details          JSON, keys allow-listed per action (A-124)
  occurred_at      RFC 3339 UTC (A-003) — displayed and differenced, never sorted on
```

- **Naming.** `<target_type>_<past participle>`, which renames release-control's five bare verbs
  (`approved` → `revision_approved`, and so on — A-120). An unregistered action raises at append.
- **Payload.** Each action declares its permitted keys. An unregistered key raises and the transaction
  fails, so a leak is a build failure at the line that wrote it (A-124). No body, fallback answer,
  credential, password, eval output, or variable *value* may appear; variable names may.
- **Scope.** `scope_prompt_id` is stamped by the appending module, which already knows which prompt it is
  acting on, making a property's Activity one indexed read instead of a five-way join it is forbidden to
  perform (A-119).
- **Order.** `seq`, always. `occurred_at` is for display and durations (A-125).
- **Target.** `(target_type, target_id)`, no foreign key, for the same reason `prompt_grant.prompt_id` is
  a value: the constraint would run against the dependency, and an audit row must outlive its subject
  (A-122).

## Alternatives rejected

**No payload — the six fields A-044 named, and nothing else.** Rejected because it makes two Success
metrics and one screen unanswerable. Without `previous_version_id` there is no restore trail; without the
role there is no role change; without `break_glass` the release trail cannot distinguish the case the
whole break-glass mechanism exists to make visible. The fields would come back as a `reason` string with
values embedded in prose, which is a payload with no schema and no allow-list.

**Free-form JSON with a redaction pass on the way in.** Rejected because it is a deny-list, and A-046
already settled that this system uses allow-lists — the same call made for upstream error bodies in
provider-access. A redaction pass strips what it was told about; the leak that matters is the field
nobody told it about, added six months later by someone debugging. This alternative is the realistic
default and losing it is the point of the ADR.

**Typed columns per event, or a table per event type.** Rejected on both halves. Thirty events give ~40
mostly-null columns and a migration for every new fact, or thirty tables — which is per-module event
tables under another name, the thing A-044 exists to prevent, and it makes the cross-module Success
queries unwritable.

**Sort by `occurred_at`, with a tiebreak on id.** Rejected because ULIDs are only monotonic within a
generator and two rows written in one transaction are the exact case that needs deciding. A sequence is
one column and removes the question. The cost — the sequence is a shared database object, so it does not
survive a split into processes — is real and is stated in A-125's revisit condition.

**Derive the prompt scope at read time by asking each module which of its ids belong to prompt X.**
Rejected as four round trips and a dependency inversion: property-history would be calling the modules
that call it, closing the cycle A-044 broke. Denormalising one id at write time, where it is already in
hand, costs nothing.

**A foreign key from `target_id` to the subject, per target type.** Rejected — see A-122. It is not
expressible against eight tables, it runs against the dependency direction, and it makes the record of a
deletion deletable by the deletion it records.

## Consequences

- One rename lands in `release-control.lock.yml` (five actions), applied there rather than left as a
  disagreement between two files.
- The allow-list is a real build-time constraint on four other modules: adding a fact to an event is a
  registry edit here plus a test, which is friction by design at the exact point where A-046's rule is
  broken.
- A prompt's Activity is `WHERE workspace_id = ? AND scope_prompt_id = ? ORDER BY seq DESC`, servable
  from one index. The release trail is the same query narrowed by target.
- `00_context.md#success` names one event, `restore_requested`, that no module writes. The real one is
  `revision_restored`. The Success table's measurement column needs correcting in the step-6 sweep;
  A-126 records the mapping meanwhile so the query is writable today.
- The vocabulary is now a fixed asset with a number attached to it — 30 — which makes "did every state
  change get an event" a countable question rather than a hopeful one.

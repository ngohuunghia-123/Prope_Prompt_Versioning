# ADR-0023 — Property History is a library in the caller's transaction, not a service

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-123)
**Module**: property-history (written while locking property-history)
**Related**: A-012, A-014, A-037, A-044, A-045, A-123, ADR-0008, ADR-0024, ADR-0025, NFR-02

## Context

Five lock files — prompt-registry, evaluation, release-control, provider-access, access-control — each
say the same sentence about their history append: *synchronous, same transaction as the state change*.
None of them says how that is possible, and it is not possible in most of the shapes a "module" can take.

The promise is doing real work. Release-control's version of it is the product claim itself: there is no
release without a trail and no trail without a release, so `00_context.md#success` can assert that 100%
of non-break-glass releases carry an approval record. Access-control's version is what makes a grant
auditable. If the append can fail independently of the change, both become "usually".

Only one arrangement delivers it. A distributed transaction is out of the question under A-012 (one
`docker-compose up`, no broker, no dedicated ops). An HTTP call inside the caller's transaction is not in
the transaction — it is a second failure domain wearing the same word. A queue is explicitly the shape
A-037 chose for *call records* and explicitly not this: a call record is telemetry that may be dropped
under load, and a history event is evidence that may not.

So the question is not "how does the module expose append" but "is this a module at all, in the sense the
other seven are".

## Decision

**Property History is a library. It has no process, no port, and no route. `append(event)` is a function
call that runs on the caller's database connection, inside the caller's open transaction, and commits or
rolls back with it.**

- The module boundary here is ownership of a schema and of an event vocabulary, not a deployment unit. It
  owns `history_event` and nothing else writes to that table.
- `read(scope)` is likewise a function call, taking a scope the caller has already permission-checked
  (A-044, A-123).
- There is no queue, no retry, no dead-letter, and no outbox. If the append fails, the state change fails
  with it — which is the whole point, and is why every dependent lock lists property-history as
  `criticality: hard`.
- It has no `/healthz` and no `/readyz`. A-045's convention is for management APIs, and this is not one.
  Its availability *is* the caller's database connection; there is nothing separate left to be up or down.
- Its metrics are emitted under the calling process's registry, labelled by the writing module.

The one consequence worth stating plainly: **this is the decision that makes the seven other modules'
"same transaction" sentences true.** If Prope is ever split across processes, that sentence becomes false
in five lock files simultaneously, and the honest migration is an outbox table in each writing module —
not an RPC that keeps the word "transaction" and drops the property.

## Alternatives rejected

**An HTTP service with `POST /events`.** Rejected because it cannot keep the promise every caller has
already made. The append becomes a second failure domain: a release commits and its event does not, or an
event is written for a release that then rolls back. Both are silent, and both destroy the only claim the
audit trail makes. Making the caller retry converts the problem into duplicate events; making the caller
fail converts an available system into an unavailable one over a log write. This is the shape most people
picture when they see eight modules on a diagram, which is exactly why it is written down as rejected.

**An asynchronous queue, following A-037's call-record pattern.** Rejected on the difference between
telemetry and evidence. A-037 chose durable-metadata / best-effort-bodies for call records because they
must not sit on the response path and a dropped body costs a debugging session. A dropped history event
costs the ability to explain a production change, and the enqueue would sit on the *management* path,
where nobody has a 50 ms budget to protect. Prope has no broker (A-012), so the queue would be a table —
at which point it is an outbox, and an outbox is strictly more machinery than writing the row.

**A database trigger on each writing table.** Rejected, and it is the closest technically correct
alternative: triggers are genuinely in the transaction. They lose the two things that make an event
useful — the actor and the reason, neither of which is a column on the row being changed — and they put
the audit vocabulary in migrations rather than in a module, where the allow-list of ADR-0024 cannot run.
A trigger also fires on writes nobody meant to audit, including backfills and repairs.

**Event sourcing: the history table becomes the source of truth and the module tables are projections.**
Rejected as a different product. It would remove the possibility of a state change without an event by
construction, which is attractive, and it would cost a rebuild of all seven other modules around
projections and replay, for a system whose ops budget is one `docker-compose up`.

**Let each module write its own history table.** Rejected by A-044 before this ADR, and worth restating
because ADR-0023 makes it briefly tempting again: if the append is just a function call in your own
transaction, why not own the table too? Because two Success metrics are queries *across* events written
by two different modules, and they cannot be run over per-module shapes. One schema is what makes the
metric computable.

## Consequences

- Every writing module links this library, and its tests run against a real database rather than a stub —
  there is no seam to mock, which is the same reason there is nothing to be flaky.
- Property History has the smallest surface in Prope and no independent failure mode. Its failure modes
  belong to its callers, which is why this lock's list is short and reads oddly compared to the other
  seven.
- Access-control's `/readyz` line — "deliberately NOT gated on property-history" — is correct and now
  correct for a stronger reason than it states: there is no separate thing to gate on. If history is
  unavailable, the database is unavailable, and access-control is down regardless.
- The claim "no release without a trail" is testable as one assertion: kill the process between the
  release row and the event, and assert neither exists.
- The condition under which this decision expires is stated rather than implied. Splitting the modules
  across processes invalidates it, and the first symptom would be five lock files quietly meaning
  something weaker than they say.

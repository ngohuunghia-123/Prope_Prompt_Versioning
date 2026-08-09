# ADR-0044 — Session rows are excluded from the backup

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: access-control — deviates from ADR-0036
**Related**: A-108, A-110, A-114, A-117, A-121, A-131, A-133, ADR-0021, ADR-0022, ADR-0025, ADR-0036,
ADR-0039

## Context

ADR-0022 is this module's headline promise: *"revoking a key, removing a member, or changing a role is
effective on the next request"*, with *"no TTL to wait out and no cache to invalidate — because there is
nothing to invalidate."* It rejected five alternatives to defend that property, including a 30-second
TTL, on the grounds that a stale answer here is a revoked credential rather than a late pointer.

ADR-0036 set the whole instance's backup at a nightly `pg_dump -Fc` with an **RPO of 24 hours**. Those
two decisions have never been read against each other. A restore rolls the `access` schema back up to a
day, which un-revokes every API key, prompt grant, role binding and membership revoked inside the window
— and brings back every session that was signed out.

The part with no cheap answer: **the `history_event` rows recording those revocations are in the same
dump and roll back with them.** After a restore there is no record inside Prope of what was revoked in
the lost window, so there is nothing to replay from and nothing to reconcile against. Everywhere else in
the system, 24 hours of loss is lost work; here it is restored access. That consequence is recorded as
**A-133** rather than engineered away, because narrowing it means a second backup schedule and closing it
means write-ahead log archiving, which ADR-0036 already declined with a named revisit trigger.

What *is* cheaply fixable is the session table, where restoring the data has no upside at all. Nobody
has ever wanted a session back. A restored session is a cookie held by somebody who signed out, or was
removed from the workspace, working again — and A-108 chose server-side rows over self-contained tokens
precisely so that *"sign-out and member removal are effective at once instead of at expiry."*

## Decision

**The nightly dump excludes `access.session`'s data:**

```
pg_dump -Fc --exclude-table-data=ledger.call_body --exclude-table-data=access.session …
```

- **Table data only**, exactly as ADR-0039 did for `call_body`. The table, its indexes and its policy
  are in the dump; only the rows are not. A restore therefore yields an empty `session` table the
  writer can insert into on the first sign-in, rather than a missing one that fails on the first write.
- The effect is that **a restore signs everybody out**, which is the correct post-restore state, and it
  is now a property of the backup artifact rather than a step in a procedure. Nobody has to remember it
  during the one operation the system performs under the most pressure and the least often.
- **Everything else in the `access` schema stays in the dump** — `user`, `workspace`, `workspace_member`,
  `role_binding`, `role_permission`, `prompt_grant`, `api_key`. Losing those is unrecoverable in a way
  losing a session never is: there is no invitation flow to re-run (A-110), a consumer key's secret
  cannot be regenerated from its row (ADR-0021), and A-117 means a workspace that loses its Admin
  bindings has no operator surface to repair it from.
- ADR-0036's restore rehearsal gains a fourth assertion beside the three it already makes: that the
  restored `session` table exists, is empty, and accepts an insert.

## Alternatives rejected

**Inherit ADR-0036 unchanged and add a post-restore runbook step** — `TRUNCATE access.session` in the
restore procedure, proven by the same rehearsal. It costs no dump flag and keeps one backup command for
the whole instance, and it was close. Rejected because it is a manual step in a procedure executed at
most once a year, during an outage, by whoever is available — and A-012's currency throughout this
project has been operations that do not need a person to be correct. A dump flag is verified every night
by the dump running; a runbook step is verified only when it is needed.

**A second, hourly dump of the `access` schema alone**, narrowing the un-revocation window from 24 hours
to one. Rejected on cost against benefit. It is a second backup job with its own schedule, retention,
destination and silent-failure mode, and ADR-0036 already had to reason once about a backup that stops
running without anybody noticing — doubling that surface to buy a *narrower* window rather than a closed
one is the wrong trade. A-131 also records that even the first destination may not exist yet. If
revocation durability ever becomes a requirement rather than a preference, the answer is the write-ahead
log archiving ADR-0036 named as its upgrade path, not a second `pg_dump`.

**Excluding the whole `access` schema from the dump.** Not seriously considered and recorded only
because it is the reflexive symmetry with `call_body`: bodies are excluded because they are best-effort
by declaration (A-037) and have no reader (ADR-0018). Nothing in `access` has either property. It holds
the only copy of who may do what, and A-121's audit trail is worthless beside a permission table that
cannot be restored.

## Consequences

- Prope now excludes exactly two things from its backup, for two unrelated reasons, and both are
  written down: `ledger.call_body` because including it would silently double a retention promise
  (ADR-0039), and `access.session` because including it would silently undo a revocation promise. The
  pattern worth carrying forward is that the dump is not neutral — it is a second lifecycle for every
  table in it.
- **A-133 records what remains.** Keys, grants, bindings and memberships revoked inside the RPO window
  come back on a restore, with no in-system record of what was lost. The revisit trigger is OQ-006's
  sign-off imposing a revocation-durability requirement, or the pilot issuing a consumer key to a party
  outside the group.
- A restore is now visible to every user rather than only to operators: everyone signs in again. That is
  a feature — a silent restore is one nobody validates — and it costs one argon2id verification per
  person at ADR-0043's cost, which is untimed and off every hot path.
- The `session` row count is the one metric that reads zero after a restore by design.
  `prope_access_control_active_sessions` dropping to 0 is expected there and is a page anywhere else.

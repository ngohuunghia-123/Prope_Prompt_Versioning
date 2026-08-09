# ADR-0036 — Backups are a nightly logical dump copied off the host

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — the Backup/DR row of all eight modules
**Related**: A-012, A-020, A-040, A-106, A-121, A-131, ADR-0025, ADR-0027, ADR-0032, ADR-0033,
ADR-0037, OQ-011, OQ-013

## Context

ADR-0033 deferred this deliberately and named where it would land:

> "Backup is not settled here. It is per-module tier and belongs with each module's datastore row — but
> the host-level fact is recorded now: `.env` must be backed up **separately from and never alongside** a
> `pg_dump`, or the backup contains both the ciphertext and its key."

property-history is the first module through Stage 2 and the strictest consumer of whatever is decided,
so the mechanism is settled here and the remaining seven modules inherit it. One PostgreSQL instance
serves all eight (ADR-0027), so there is one mechanism regardless; what varies per module is tolerance,
and this module has the tightest. A-121 states there is *"no retention setting and no expiry job"* —
every history row is meant to exist forever, which makes every lost row lost permanently rather than
lost until the next write.

The decision also has an edge the other seven modules do not: **a restore is the one operation that can
un-write the record ADR-0025 spent a privilege protecting.** Restoring a three-day-old dump silently
deletes three days of audit events, and it leaves no trace of having done so — the exact failure mode
`REVOKE UPDATE, DELETE` exists to prevent, arriving through the recovery path instead of the
application.

Two constraints bound the answer. A-012: *"the team is small with no dedicated ops"* and no component
may need its own runbook. And A-020: *"no real corporate prompts until the security baseline is signed
off"* — during the pilot there is, by policy, nothing evidentiary in the table yet.

## Decision

**A nightly `pg_dump -Fc` of the whole instance, copied to a second machine the group controls, retained
30 days. RPO 24 hours, RTO roughly 10 minutes.** One cron entry and one copy step; no new component, no
new service, no new container.

Specifically:

- **Custom format** (`-Fc`), whole instance, taken as the `postgres` superuser on the host — not as
  `prope_app`, which ADR-0035 makes RLS-subject and would therefore dump zero rows from every
  workspace-scoped table, and not as ADR-0037's `prope_report`, which is `SELECT`-only and cannot dump
  schema.
- **Off-host means a second machine the group controls.** Object storage is excluded — see below.
- **`.env` is backed up to a different destination on a different schedule** (ADR-0032, ADR-0033).
  A dump and a KEK in one archive is envelope encryption with the envelope taped to the letter.
- **The restore is rehearsed once before the pilot opens**, into a scratch database, and the rehearsal
  asserts three things rather than "it restored": ADR-0025's `REVOKE` survives the round trip,
  ADR-0035's policies are present and enabled on every restored table, and ADR-0037's roles exist. A
  logical dump carries grants and policies, but a restore into a cluster missing the roles produces a
  table whose protections quietly did not apply.
- **A restore is a deployment action with the same posture as `prope_migrate`** — deliberate, announced,
  and followed by a written note of what window was lost. It is not a repair tool.

## Alternatives rejected

**WAL archiving / point-in-time recovery** (pgBackRest, wal-g, or a plain `archive_command` plus a
periodic base backup). Rejected for the pilot, not on merit. It is the technically better answer — RPO
of minutes rather than a day — and it is what a real corporate dataset would deserve. It loses on two
counts. It is a second component with a restore procedure that is only trustworthy if rehearsed, which
is precisely the *"no component needing its own runbook"* clause A-012 exists to spend carefully. And it
is **cheap to add later**: enabling `archive_mode`, pointing `archive_command` somewhere, and taking a
fresh base backup involves no schema change, no data movement, and no application change. That is the
same retrofit-asymmetry test that deferred Loki (ADR-0030) and cloud KMS (ADR-0032) while adopting
schema-per-module (ADR-0027) and RLS (ADR-0035) immediately. Its revisit trigger is A-020's sign-off —
the moment real corporate prompts enter, a 24-hour RPO stops being embarrassment and starts being data
loss somebody else owns.

**A nightly dump written to the same VM only.** Rejected because it protects against the wrong half of
the risk. It covers a bad migration or a dropped table, which are the likely pilot failures — and it
covers nothing about losing the host, which under A-121 means losing every audit event Prope has ever
recorded. ADR-0033 accepted a single failure domain explicitly, but for **availability**:
`00_context.md#scope` calls it *"an accepted risk, not a mitigated one"* in the context of downtime.
Extending that acceptance to permanent data loss is a different trade that nobody made.

**Object storage as the off-host destination** (S3, B2, R2, or similar). Rejected on residency, and this
is the reason worth writing down because the option is otherwise the obvious one — it is cheap,
durable, and one `rclone` line. A dump contains prompt bodies, stored request and response bodies
(ADR-0018, A-040), and encrypted provider credentials. Sending it to a vendor bucket puts all of that in
a third party's data plane in an unnamed region, which is what ADR-0030 refused for telemetry and
ADR-0033 refused for managed PaaS, and it contradicts OQ-011's resolution outright — that question was
answered *"by consequence: nothing leaves the host."* A backup channel is not an exception to a
residency answer; it is the largest single instance of it. If OQ-013 later rules that a
customer-managed encrypted bucket is acceptable, this becomes the natural destination and the change is
one line.

## Consequences

- **Up to 24 hours of history can be lost, permanently, and no compensating event will record that it
  happened.** Stated plainly because A-121's "never deleted" is a product claim and this is its
  exception. During the pilot A-020 makes the loss non-evidentiary; after sign-off it does not, and that
  is the revisit trigger.
- Every module's Backup/DR row cites this ADR. `call-ledger` is the one with a different problem rather
  than a different tolerance: its `call_body` is the only unbounded disk term (ADR-0033), so its pass
  decides whether bodies are in the dump at all or excluded and left to A-040's retention.
  **Settled, and it happened twice.** ADR-0039 excluded `ledger.call_body`'s data because including it
  would silently extend a 30-day retention promise to 60 while the gauge watching that promise read the
  live table and reported green. ADR-0044 then excluded `access.session`'s data because including it
  would silently undo ADR-0022's revocation promise. Both use `--exclude-table-data` rather than
  `--exclude-table`, so a restore yields an empty table the writer can insert into. The generalisation
  worth carrying into the remaining module passes: **this dump is a second lifecycle for every table in
  it**, and a table whose value comes from being deleted or revoked is the kind that does not want to be
  in it. A-133 records the part of that collision no exclusion fixes — revocations inside the RPO come
  back, and their history events roll back too.
- The dump is the second place, after the database itself, where a full copy of everything sensitive in
  Prope exists. It inherits the same handling rules as the disk it came from, and the destination
  machine inherits them too.
- **A second group-controlled machine is now a pilot prerequisite.** If none exists when the pilot
  opens, A-131 records what happens instead — the dump is written locally and copied by hand at pilot
  review — as a gap with a name rather than an omission.
- The restore rehearsal is the only place the ADR-0025 / ADR-0035 / ADR-0037 interaction is checked end
  to end. A dump that restores cleanly into a cluster with no `prope_app` role produces a table with no
  policy applied and no `REVOKE` in force, and nothing else in the build would notice.

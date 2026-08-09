# ADR-0039 — `call_body` is excluded from the backup

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: call-ledger — a deviation from ADR-0036's whole-instance dump
**Related**: A-020, A-037, A-040, A-105, A-106, A-131, ADR-0018, ADR-0033, ADR-0036, OQ-013

## Context

ADR-0036 settled backup as a nightly whole-instance `pg_dump` copied off-host with 30-day retention.
Applied unchanged to this module it produces a result nobody chose: **A-040 sets body retention to 30
days, so a body deleted on day 30 lives in an off-host archive until day 60.** The real retention is the
body window plus the backup window, and every number stated in the product means something other than
what it says.

The guard cannot see it. `LedgerRetentionOverdue` reads `prope_call_ledger_oldest_body_age_seconds`,
which measures the live table. Throughout the thirty days a body sat in an archive the alert reports
green — the same failure shape the lock already identified for the deletion job itself:

> "Deliberately measured on the DATA rather than on the job: a deletion job that runs successfully every
> night and deletes nothing looks healthy from the job's side and is the exact way a retention promise
> quietly stops being true."

`call_body` is also the only unbounded disk term in the system — roughly 3 GB/month at 10k calls/day
(ADR-0033) — so including it makes the nightly dump the largest recurring operation on the host, in
service of data that nothing reads.

## Decision

**The nightly dump runs with `--exclude-table-data=ledger.call_body`.** Table *data* only: the schema,
indexes, constraints and grants are still dumped, so a restore produces an empty `call_body` rather than
a missing one, and nothing downstream has to know the table was special.

Everything else in the module is backed up normally — `call_record`, `price_table`, `workspace_spend`,
`spend_ceiling`. Those are the audit trail NFR-02 requires and the pricing history ADR-0019 makes
permanent, and none of them carries end-user content.

The justification is that bodies already have a declared durability class, and it is not "durable".
A-037 drops them first under pressure and counts it. ADR-0018 gives them no reader at all — no endpoint,
no export, no admin viewer, no join. **A datum that is best-effort by design and has no read path does
not earn a second copy**, and the second copy is the one place the retention policy does not reach.

## Alternatives rejected

**Include bodies and shorten backup retention below the body window.** Rejected on a coupling that
cannot hold. A-106 makes retention a **per-workspace** setting, deliberately: *"a setting from day one so
OQ-013's answer is a configuration change, not a migration."* A host-level backup cron would therefore
have to track the shortest window any tenant has chosen, and would break silently — not loudly — the
first time somebody sets 7 days. It couples an operations schedule to a tenant preference, which is a
dependency in the wrong direction and invisible when violated.

**Include bodies and document the 60 days.** Rejected, though it is the most honest of the three and the
easiest to operate. The cost is that OQ-013 — already rated Critical and already the module's single
largest risk — would have to answer for two locations with different lifecycles, and the alert designed
to prove the policy is being kept would be measuring the smaller one. A retention promise whose stated
number is never the real number is worse than a shorter promise kept exactly.

**Exclude the whole table, schema included.** Rejected as a needless sharp edge. A restore would then
produce a database where the writer's first body insert fails, turning a recovery into an outage over a
table whose contents were disposable anyway.

## Consequences

- **After a host loss, no request or response body is recoverable.** Stated plainly. Metadata,
  pricing, spend totals and every audit trail survive; the bodies do not. That is the same trade A-037
  makes under queue pressure, extended to the same data for the same reason.
- **OQ-013's answer now governs one location.** Retention, PII, redaction and residency apply to
  `ledger.call_body` and to nothing else — no archive copy, no second lifecycle, no second policy. This
  narrows the question and is recorded in its file.
- The nightly dump stays small and fast. What remains is metadata and configuration, which grows with
  call *count* rather than with body *size*, so ADR-0036's 24-hour RPO does not turn into a multi-hour
  copy as traffic grows.
- The backup host's handling requirements drop accordingly. It still holds prompt bodies and encrypted
  credentials — A-131's rules stand unchanged — but it no longer holds raw end-user request and response
  content, which was the largest single reason to worry about where it lives.
- A future body-read surface, if OQ-013 permits one, does not change this ADR. Bodies would still be
  best-effort and still self-delete; a reader gives them a consumer, not a durability class.

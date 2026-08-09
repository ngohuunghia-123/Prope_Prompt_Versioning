# ADR-0040 — The ledger writer batches per workspace, so RLS holds on the highest-volume writer

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: call-ledger — and the pattern for any future cross-tenant batched writer
**Related**: A-098, A-099, A-103, A-106, ADR-0018, ADR-0027, ADR-0028, ADR-0035, ADR-0037, ADR-0041,
BR-01

## Context

ADR-0035 sets the tenant context with `SET LOCAL app.workspace_id` **per transaction**, and makes
`prope_app` subject to a policy carrying both `USING` and `WITH CHECK`. Every module in Prope satisfies
that trivially, because every module serves one request for one workspace inside one transaction.

call-ledger does not. Its writer drains a queue holding records from **many workspaces at once** and
inserts them in batches, against a stated target of *"≥ 500 records/sec sustained, batched inserts,
single writer"* — a target whose margin the lock calls the point:

> "A writer that merely keeps up has no capacity to clear a backlog after a stall, so every stall
> becomes permanent pressure."

One `SET LOCAL` cannot cover a batch spanning tenants. So either the batching changes or the isolation
does, and this is the only place in the system where that question arises. The same question decides the
retention job (A-106), which deletes expired bodies across every workspace at once.

There is a second gap underneath it. **`call_body` carried no `workspace_id`** — its fields were
`call_id, request_body, response_body, byte_size, expires_at, created_at`, with the tenant reachable
only by joining `call_record`. ADR-0035's CI test enumerates tables *carrying* `workspace_id` and
asserts a policy on each, so as written it would have skipped the one table in Prope holding raw
end-user content.

## Decision

**The drain groups each batch by `workspace_id` and opens one transaction per workspace**, each with its
own `SET LOCAL app.workspace_id` and a single multi-row insert. The retention job does the same: it
iterates workspaces and deletes each one's expired bodies in bounded chunks inside that workspace's
transaction.

**`call_body` gains a `workspace_id` column**, stamped by the writer, which already has it. This is a
lock-file amendment to `data.owns`, recorded there. It costs 16 bytes on the largest table and buys
three things: ADR-0035's policy and CI test reach the table automatically, the retention job has a
per-workspace predicate that uses an index rather than a join, and a future body reader — if OQ-013 ever
permits one — inherits tenant isolation instead of retrofitting it onto the highest-liability data in
the product.

No new role, no `BYPASSRLS` anywhere on the write path. The cost is N transactions per drain cycle where
N is the number of *distinct workspaces in that batch* — a figure that scales with tenant count, not
with traffic, and is small at pilot scale. A-103's monthly aggregate update was already per-workspace,
so it falls inside the same transaction naturally rather than needing its own.

## Alternatives rejected

**A fourth role, `prope_writer`, with `BYPASSRLS` and INSERT-only on the ledger schema.** Rejected on
what it gives up rather than on cost — it is genuinely the fastest and the simplest code. It would make
the process that writes more rows than anything else in Prope the one process outside tenant isolation,
and it would retire `WITH CHECK` precisely where the guard earns most. A call record's `workspace_id` is
supplied by a caller that denormalised it from somewhere else; a mis-stamped one is the realistic
cross-tenant leak in this module, and `WITH CHECK` is what makes it a refused insert rather than another
workspace's traffic in someone's spend total. It is also a fourth database role two ADRs after
ADR-0027's title said two, and unlike ADR-0037's `prope_report` it would be used by running application
code rather than by a person.

**One transaction per record.** Rejected on the throughput margin. It satisfies RLS with no grouping
logic and no new column, and it abandons batched inserts entirely — which is not a 20% cost but the
difference between a writer that can clear a backlog and one that cannot. The lock is explicit that the
margin, not the rate, is what the target is for.

**A policy that permits an insert when `app.workspace_id` is unset.** Rejected as a hole wearing a
policy's clothes. Any code path that forgets the `SET LOCAL` would then write successfully, which is the
exact failure mode ADR-0035 was written to convert into zero rows.

## Consequences

- **The drain's transaction count scales with tenant count, not with traffic.** A workspace-heavy
  future — many small tenants rather than a few busy ones — is where this decision starts to cost, and
  that is the revisit trigger: the drain's per-cycle transaction count, visible in
  `prope_call_ledger_written_total` against write lag.
- The grouping is a correctness requirement, not an optimisation. A drain that stops grouping does not
  get slower; it gets refused by the database, which is the intended direction.
- `call_body.workspace_id` is denormalised and never joined for authorisation. It is the tenant key for
  a policy and a predicate, consistent with the module's existing posture — `prompt_id`, `version_id`,
  `revision_number` and `upstream_model` are all values rather than references, so the trail survives
  independently of the registry's current state.
- ADR-0035's CI test now covers `ledger.call_body`. Nothing had to change in the test; the column is
  what brings the table into its enumeration, which is the property that made adding the column cheaper
  than special-casing the table.
- ADR-0041's fallback path inherits this rule. A direct write from the `app` process is a single-record
  single-workspace transaction, so it satisfies `SET LOCAL` by construction and needs no exception.

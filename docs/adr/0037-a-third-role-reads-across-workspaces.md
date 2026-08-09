# ADR-0037 — A third role, `prope_report`, reads across workspaces

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — extends ADR-0027
**Related**: A-121, A-126, A-131, ADR-0025, ADR-0027, ADR-0031, ADR-0035, ADR-0036, OQ-013

## Context

ADR-0035 made `prope_app` subject to row-level security. That closed the tenancy hole it was written
for and opened a small operational one nobody had to think about before: **a query that is supposed to
span workspaces now returns zero rows.**

Two such queries already exist in the specification. A-126 records that the two audit-event Success
metrics — restore time and review turnaround — are *"hand-run SQL at pilot review, not product
surfaces"*. Both are computed across the whole pilot, not per workspace. And ADR-0036's dump is a
cross-workspace read by definition.

Before this ADR, the only credential that could satisfy either was `prope_migrate`. That role owns the
tables, so it bypasses RLS — and ADR-0025 deliberately gave it the one power no other role has:

> "Migrations run under a separate role that does hold those privileges. A genuine correction is
> deliberate, visible, and outside the application."

The value of that sentence is entirely in how rarely the role is used. A monthly metrics query is not a
genuine correction, and routing it through the correction credential makes reaching for the only key
that can `DELETE` a history row an ordinary Tuesday. The erosion is invisible: nothing breaks, no test
fails, and six months later an unexplained `prope_migrate` session in the logs is no longer a signal
because there are forty of them.

This is a property-history-shaped problem specifically. In every other module a stray privileged session
is a risk; here it is the module whose entire product claim is that the record cannot be quietly
rewritten.

## Decision

**A third role, `prope_report`: `LOGIN`, `BYPASSRLS`, `SELECT` only. No DDL, no `INSERT`, no `UPDATE`,
no `DELETE`, on any table in any schema.** One statement pair in a migration; no connection pool, no
application code, and nothing in the running system uses it.

It is for humans running ad-hoc and scheduled reads across workspaces — A-126's Success metrics, pilot
review queries, and any future reporting surface that needs the whole instance.

Explicitly **not** what ADR-0027 rejected. That ADR turned down role-per-module because it means eight
credentials and eight connection pools carried by the application. This is one login role for people,
outside the application entirely, and it moves no data and changes no schema.

`prope_migrate` keeps `BYPASSRLS`-by-ownership and its `UPDATE`/`DELETE` grant, and is used only by
ADR-0031's migration step and by a genuine correction. ADR-0036's dump continues to run as the host
`postgres` superuser, because a `SELECT`-only role cannot dump schema.

## Alternatives rejected

**Use `prope_migrate` for reporting.** Rejected on the erosion above. It is free today and costs the
distinction ADR-0025 drew, which is the distinction the product's central claim rests on. The specific
loss is auditability of the audit log: with one privileged role used for two purposes, no session
record distinguishes a person reading a metric from a person editing a row, and the second is exactly
what a reader of the trail would want to know about.

**Query per workspace as `prope_app`, setting `app.workspace_id` each time.** Rejected on both halves.
It is the strictest posture — no `BYPASSRLS` exists anywhere — but the metrics A-126 names are
pilot-wide by construction, so it becomes N queries and a hand-assembled union that will be wrong the
first time a workspace is added and forgotten. And it means a person holding the application's own
database password, which is a worse outcome than the one being avoided: that credential can write to
every table in the system.

**A read-only role without `BYPASSRLS`, plus a permissive policy naming it.** Rejected as the same
capability with more moving parts. A `USING (true)` policy for the reporting role must be added to every
workspace-scoped table and kept in step as tables are added — a per-table obligation that will drift,
producing a reporting role that silently sees six of eight modules. `BYPASSRLS` is one role attribute
that cannot partially apply.

## Consequences

- **Prope now has three database roles with three different jobs**: `prope_app` writes at runtime and is
  RLS-subject; `prope_migrate` changes structure and is the only role that can alter or remove a history
  row; `prope_report` reads everything and changes nothing. Each is a different answer to "what could
  this credential do if it leaked," which is the property the split exists to create.
- **ADR-0027's title says "two roles" and is now incomplete.** A pointer note is added there rather than
  superseding it — schema-per-module and the two application roles stand entirely, and this adds a role
  no application uses.
- An unexpected `prope_migrate` session remains a signal worth investigating. That is the whole return
  on this decision, and it only holds if `prope_report` is actually used for reporting; a habit of
  reaching for `prope_migrate` because it is already in someone's shell history defeats it.
- `BYPASSRLS` means this credential reads every workspace's prompt bodies, call bodies, and history.
  It is a full-read credential and is handled as one: not in CI (ADR-0031), not in `.env` alongside the
  application's (ADR-0032), and issued to a person rather than to a process.
- ADR-0036's restore rehearsal now checks that this role exists in the target cluster, because a dump
  restored without it produces grants referring to a role that is not there.

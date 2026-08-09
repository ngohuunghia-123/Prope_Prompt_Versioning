# ADR-0035 — Tenant isolation is a database policy, not a `WHERE` clause

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — every table carrying `workspace_id`
**Related**: A-109, A-116, A-118, A-119, A-122, ADR-0002, ADR-0019, ADR-0020, ADR-0023, ADR-0025,
ADR-0027, BR-01, BR-03, OQ-007, OQ-013

## Context

Prope is already almost entirely multi-tenant. A-109 makes `workspace` *"the tenancy root every
workspace_id refers to"*, every module's owned tables carry `workspace_id`, and the indexes the locks
declare already lead with it — `(workspace_id, scope_prompt_id, seq DESC)`,
`(workspace_id, target_type, target_id, seq DESC)`, and so on. `00_context.md#scope` puts
*"multi-region or multi-tenant routing"* out of scope, but that is routing, not data.

What is missing is enforcement. Today tenant separation is a `WHERE workspace_id = ?` that a developer
must remember on every query, in every module, forever. The failure mode of forgetting it is a
cross-tenant data leak — and it is a *silent* one, because a query that returns another workspace's rows
looks like a query that worked.

That is the same class of defect this project has now rejected three times. BR-03 — the rule that *is*
the product — is enforced by a database constraint rather than application code. ADR-0025 made
append-only a database privilege because *"application code that intends not to update a table is one
ORM call away from updating it."* ADR-0027 chose schema-per-module over a shared schema because a
boundary nothing enforces is a boundary nobody keeps. Tenancy is the strongest instance of the pattern
and the only one still resting on convention.

A related pressure sharpens it. `00_context.md` describes an internal group tool — OQ-007 (*"Is
individual mode in this MVP, or is the build enterprise-only?"*) is still open, and whether Prope
becomes a product sold to strangers is a `00_context.md` question rather than a step-4 one. But the
*data-layer* consequence of that question is not deferrable on the same terms: enabling row-level
security on day zero costs a policy per table, while retrofitting it means a migration per table plus a
re-audit of every query path with real customer data already in the box.

## Decision

**Every table carrying `workspace_id` has row-level security enabled, with a policy binding it to a
session variable. `prope_app` is subject to the policy; `prope_migrate` owns the tables and bypasses
it.**

- The policy is `workspace_id = current_setting('app.workspace_id')::uuid`. The application sets
  `SET LOCAL app.workspace_id = …` inside the transaction, so it is scoped to that transaction and safe
  under connection pooling.
- **ADR-0027's two-role model is what makes this work without a third role.** A table's owner bypasses
  row-level security by default; `prope_migrate` owns every table and `prope_app` owns none, so the
  runtime role is subject to policy and the migration role is not, with no additional grant machinery.
- **The failure mode inverts, which is the entire point.** A query missing its filter today returns
  another tenant's rows. Under this policy it returns **zero rows** — visible, wrong in the safe
  direction, and caught by the first test that expects data.
- **It composes with ADR-0023 rather than fighting it.** Property-history's `append()` runs on the
  caller's connection inside the caller's transaction, so the session variable the caller set already
  applies. The history write is tenant-scoped by the same mechanism as the state change it records,
  which is the correct outcome and requires no special case.
- Genuinely cross-workspace work — the pilot-review SQL in A-126, the retention job in A-106 — runs
  outside the request path under a role that bypasses the policy, and is written knowing it does.
- **This is enforcement, not a replacement for the application's own filtering.** Queries keep their
  `WHERE workspace_id = ?` where it aids the planner and expresses intent. The policy is the backstop
  for the day somebody forgets, which is the day it matters.

## Alternatives rejected

**Application-level filtering only, enforced by review and tests.** Rejected as the status quo that
prompted the ADR, and rejected on precedent: it is the enforcement model BR-03, ADR-0025 and ADR-0027
each declined for weaker stakes. It cannot be tested for in any meaningful way — one can assert that
today's queries filter correctly, which says nothing about tomorrow's. And its failure is silent and
unbounded, which is the worst combination available: a missing filter produces plausible-looking data
from the wrong workspace, and BR-01's *"prompts are private by default"* is a non-negotiable row that
this would quietly break.

**A database or schema per workspace.** Rejected on three counts. It breaks ADR-0023 for any operation
spanning workspaces and makes connection management a function of customer count. It multiplies
migrations by tenants, so ADR-0031's single migration step becomes a fan-out that can partially fail. And
it is a poor fit for a pilot whose tenant count is small and whose isolation requirement is logical
rather than physical — while being far harder to *undo* than row-level security is to add.

**Deferring the decision until OQ-007 says whether Prope is a SaaS product.** Rejected on asymmetry,
which is the argument that carried it. Adopting the policy now costs one line per table in the initial
migration and a `SET LOCAL` in the transaction helper. Adopting it after data exists costs a migration
per table, a re-audit of every query path in eight modules, and the session plumbing anyway — performed
under the pressure of whatever prompted it. The policy is also worth having for a purely internal
multi-workspace tool, so it does not depend on OQ-007's answer to pay for itself.

## Consequences

- Every migration that creates a `workspace_id` table also enables row-level security and creates its
  policy. **Amended 2026-08-09 by ADR-0042** — the enumeration below turned out to have two gaps, both
  found while locking access-control's stack. `prompt_grant` carried no `workspace_id` at all, so the
  test skipped the table implementing BR-01; it now has the column. And `workspace` has no
  `workspace_id` column because its **primary key is** the workspace id, so **the test needs a second
  clause** or it silently skips the tenancy root. ADR-0042 also records the only sanctioned bypass of
  this policy anywhere in Prope: two `SECURITY DEFINER` functions on the authentication seam, because
  `session` and `api_key` are read *before* `app.workspace_id` exists — they are the reads that produce
  it. A third such object is a test failure by design.
  **Superseded again 2026-08-09 by ADR-0045, which is the last word on this.** ADR-0042 patched the
  test; the very next module pass found a third instance of the same shape (`provider.credential`), so
  the *rule* was wrong rather than the instances. The test no longer enumerates tables that carry
  `workspace_id` — it walks **every** table in the eight module schemas and requires each to be
  tenant-scoped or listed in `GLOBAL_TABLES` with a written reason. The decision below — the policy, the
  session variable, `SET LOCAL` per transaction, the failure inverting to zero rows — is untouched. Only
  *which tables are checked* changed.
  Forgetting the policy is the new silent failure, and it is caught by a CI test that enumerates
  tables carrying `workspace_id` and asserts each has row-level security enabled with a policy — the
  same shape as ADR-0025's privilege test.
- All database access goes through a transaction helper that sets the session variable. Direct
  connection use bypasses that helper and therefore returns nothing, which is a loud and instructive
  failure rather than a dangerous one.
- The planner sees the policy predicate on every query. Because every declared index already leads with
  `workspace_id`, this is close to free — the locks made that choice for their own reasons and it pays
  again here.
- A-116's not-found-versus-forbidden rule is unaffected: it governs subjects the actor may not see
  *within* a workspace, and this policy governs the workspace boundary itself. They stack; neither
  replaces the other.
- If OQ-007 later makes Prope a product sold to strangers, the data layer is already correct, and the
  remaining work — signup, billing, availability commitments, a marketing surface — is additive rather
  than a migration.

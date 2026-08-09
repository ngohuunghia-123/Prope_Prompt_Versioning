# ADR-0051 — The cross-tenant sweep enumerates workspaces; the data reads stay under policy

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: release-control — extends ADR-0042's set to four and generalises it for every future sweep
**Related**: A-009, A-012, A-014, A-072, A-073, A-140, ADR-0008, ADR-0026, ADR-0027, ADR-0028,
ADR-0030, ADR-0033, ADR-0037, ADR-0042, ADR-0045, ADR-0049, OQ-006, OQ-012,
`00_context.md#constraints`, `00_context.md#success`

## Context

Release-control has two pieces of work that never run inside a request, and both were written into its
lock before a tenancy mechanism existed:

- **the reconciliation query** — *"prompt properties whose `released_version_id` has no matching release
  row — run on startup and hourly"*;
- **`prope_release_review_task_open` and `prope_release_review_task_overdue`**, the gauges behind the
  `BreakGlassTaskOverdue` alert.

Both must see every workspace at once. **ADR-0045 makes that return nothing.** Under deny-by-default
row-level security, a `prope_app` query issued with no `app.workspace_id` in the session returns **zero
rows** — which is the policy working exactly as designed, and which here produces a gauge that reads `0`
forever.

That is not a cosmetic failure. This module's own lock states what the gauge is for:

> "The task never auto-closes and never expires; it stays overdue and counted. Its only exit is a
> recorded decision by someone. **The overdue gauge is the number that shows whether the gate is real.**"

Break-glass is the one path in Prope that reaches production with no approval record
(`00_context.md#constraints`: *"Human approval is mandatory before a revision is promoted to
production"* — break-glass is the declared, counted exception, A-009). The 24-hour follow-up task is the
entire mechanism that keeps it exceptional. An unscoped sweep would report that mechanism healthy at all
times, including the times it was not.

This is the same defect class ADR-0049 found in evaluation's claim loop one pass earlier — a background
process that must discover its own work across tenants — with one difference worth recording: **that one
was found while writing the block, this one while grilling it.**

## Decision

**A single sweep job runs in `worker`. It obtains the tenant list from a `SECURITY DEFINER` function that
returns workspace identifiers and nothing else, then issues `SET LOCAL app.workspace_id` per workspace
and runs its actual queries under ordinary policy.**

```sql
CREATE FUNCTION access.list_workspaces() RETURNS SETOF text
  LANGUAGE sql
  SECURITY DEFINER
  SET search_path = ''
AS $$ SELECT id FROM access.workspace $$;

ALTER FUNCTION access.list_workspaces() OWNER TO prope_migrate;
REVOKE EXECUTE ON FUNCTION access.list_workspaces() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION access.list_workspaces() TO prope_app;
```

- **The set of sanctioned policy bypasses becomes four.** `access.lookup_session` and
  `access.lookup_api_key` (ADR-0042), `evaluation.claim_next_run()` (ADR-0049), and this one. All four
  are owned by `prope_migrate`, carry an empty `search_path`, are `REVOKE`d from `PUBLIC`, `GRANT`ed to
  `prope_app`, and return only identifiers. The CI test that asserts the set is *exactly* these is
  updated to four.
- **ADR-0042's general form extends.** That ADR's rule was *a read that must run before a tenant is
  known, because it is what produces the tenant*. ADR-0049 widened it to *a background worker that
  discovers its own work across tenants needs the same escape an authentication bootstrap needs*. This
  ADR adds the constraint on **shape**: **a function that returns tenant identifiers keeps every
  subsequent data read under RLS; a function that returns rows does not.** The bypass should be as close
  to `SELECT id` as the job allows.
- **One function, not one per sweep.** Every future cross-tenant background job in Prope reuses this one
  and adds nothing to the bypass set. That is what keeps *"the set is exactly N"* a meaningful assertion
  rather than a number tracking feature count.
- **The job is a plain `asyncio` task in `worker`**, matching call-ledger's retention job and
  evaluation's sweeper. Gauges refresh every 60 s; the reconciliation query runs at startup and hourly.
  No scheduler library enters the build for a third timer.
- **`worker` is where it belongs.** `app` holds the gateway's p95 budget, and ADR-0046 and A-130 are both
  arguments for moving work out of that process rather than into it. `worker` already hosts every
  scheduled job in the build. The gauges are exported from `worker`'s scrape target, which Prometheus
  already reads for call-ledger's drain metrics (ADR-0030).

### What the reconciliation query is now for

Its stated purpose was: *"The pointer command and the release row commit in one transaction against one
database (A-012 — one process, one Postgres, no broker, so this is a local transaction and not a
distributed one). The reconciliation query is the tripwire that proves the assumption still holds after
step 4 chooses the stack."*

**Step 4 chose the stack and the assumption held.** ADR-0026 put all eight modules in one process and
ADR-0027 put them on one database, so the orphaned-pointer scenario — a registry command committing while
release-control's own transaction fails — **cannot occur**. It is one local transaction. A-130's proposed
gateway split does not disturb it either: the gateway is the process that leaves, and release-control,
prompt-registry and property-history stay together in `app`.

The query survives, and it survives for a different reason than the one it was written for. What it now
detects is a **released pointer written by something other than a release** — the residual exposure
ADR-0008's amendment names, once one process and one role reduced *"writes no table it does not own"* from
a seam to a checked convention. CI catches the shape; this query catches the instance. That is the same
move A-063 made one pass earlier, surviving for measurement rather than for the reason it was created.

## Alternatives rejected

**A purpose-built `SECURITY DEFINER` function per sweep** — `release.find_orphaned_pointers()` and
`release.count_open_review_tasks()`, each narrow and named for its job. This is the closer reading of
ADR-0049's `claim_next_run()`, and it was the starting proposal. Rejected on two counts. First, both would
return **content** rather than identifiers, so the data read happens *inside* the bypass instead of under
policy — the anti-join reads `registry.prompt_property` and `release.release` across every tenant with
RLS disabled, and a defect in the function body is a cross-tenant read with no second line of defence.
Second, the set grows by one function per sweep per module, forever; ADR-0042's test asserting the bypass
set is exactly N stops being a control the moment N tracks feature count rather than architecture.

**Give the job `prope_report` credentials.** ADR-0037 already created a `LOGIN` + `BYPASSRLS` +
`SELECT`-only role for exactly this class of read, so this adds no new object and no new pattern.
Rejected because it puts a `BYPASSRLS` connection string in `.env` and in a running process: a compromised
`worker` then reads every workspace's prompts, approvals, reasons and comments with one credential, where
today it would have to defeat a policy per query. ADR-0037's own closing line is the control being spent —
*"No application code uses the third"* — and this module's data is the worst place to spend it, because
`approval.comment` and `release.reason` are the free-text human sentences A-046 keeps out of log lines
precisely because they can name a customer or an incident.

**A `postgres_exporter` sidecar running the queries as `prope_report`.** The conventional answer, and it
keeps the bypass out of the application entirely. Rejected on operational shape: it is an eighth container
on ADR-0033's single 4 vCPU VM, it carries the same `BYPASSRLS` credential as the option above, and it
moves the definition of `BreakGlassTaskOverdue`'s input out of the codebase into exporter configuration —
so a query the product's central control depends on stops being covered by a test, a review, or ADR-0031's
build.

## Consequences

- **The sanctioned bypass set is four, and the shape rule is now written down.** Any fifth is read the
  way `GLOBAL_TABLES` entries are read: it must return identifiers, be owned by `prope_migrate`, carry an
  empty `search_path`, and have a reason in an ADR.
- **`release-control` runs in `worker`** — the sixth module to do so, and the second (after evaluation)
  with no RabbitMQ involvement at all. `events.publishes` and `events.subscribes` both stay `[]`.
- **The sweep's own failure is a new failure mode with weak detection.** If the task dies, the gauges
  freeze at their last value rather than dropping to zero, so `BreakGlassTaskOverdue` neither fires nor
  visibly breaks. A sweep-heartbeat counter is recorded as owed alongside it — a stale gauge and a healthy
  one look identical, which is the property that made this defect worth finding in the first place.
- **Two acceptance criteria are owed** (AC-13, AC-14): that the sweep counts an overdue task belonging to
  a workspace no request has touched, and that the reconciliation query finds a hand-written pointer.
- **N+1 transactions per sweep pass**, one per workspace, unbounded in workspace count. Trivial at the
  pilot's shape and recorded rather than guessed at — **A-140**, against an OQ-012 that has now been silent
  for five consecutive passes.
- The function enumerates tenants. A caller that already holds `prope_app` can therefore list workspace
  ids; it cannot read a row of any of them without a policy match, which is the property the shape rule
  exists to preserve.

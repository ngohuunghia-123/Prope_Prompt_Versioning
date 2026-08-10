# ADR-0042 — The authentication bootstrap escapes row-level security through two named functions

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: access-control — and every future pre-tenant lookup, which will copy this shape
**Related**: A-081, A-108, A-109, A-112, A-113, A-116, ADR-0020, ADR-0021, ADR-0022, ADR-0027,
ADR-0029, ADR-0035, ADR-0037, ADR-0040, BR-01

## Context

ADR-0035 put row-level security on *"every table carrying `workspace_id`"*, bound to
`current_setting('app.workspace_id')::uuid` and set per transaction with `SET LOCAL`. It composes
cleanly with every module written since — because every one of them runs *after* the request's tenant
is known.

Access-control is where that stops being true. It owns the eight tables that establish tenancy, and
enumerating them against the policy's shape splits them four ways:

| Table | Carries `workspace_id` | Under ADR-0035 as written |
|---|---|---|
| `session` | yes | policied — **and unreadable at authentication time** |
| `api_key` | yes | policied — **and unreadable at authentication time** |
| `workspace_member`, `role_binding` | yes | policied, correctly, no issue |
| `user` | no | no policy, and correctly so — `unique(email)` is global, a person is not a tenant's property |
| `role_permission` | no | no policy, and correctly so — the `(role, action)` matrix is one global table |
| `workspace` | no — its **primary key** is the workspace id | **skipped entirely by ADR-0035's enumeration**, though it is the tenancy root |
| `prompt_grant` | **no, and it should** | **skipped**, though it implements BR-01's private-by-default grants |

Two distinct problems.

**The bootstrap deadlock.** `authenticate_session(cookie)` reads `session` by id and
`authenticate_api_key(secret)` reads `api_key` by the `key_id` embedded in the presented secret
(A-113). Those two reads are what *produce* `app.workspace_id`; they cannot consume it. Under the
policy with nothing set, `current_setting('app.workspace_id')` raises `undefined_object` — and with the
two-argument missing-ok form it returns NULL, so the comparison is NULL and the row is filtered out.
Either way the answer is no rows, and the consequence is not local to this module: **every
authenticated request in Prope fails, including every gateway call.** This surfaces on the first
development run rather than in production, but the *shape* of the escape hatch is architectural, because
it is the precedent every later pre-tenant lookup will follow.

**Two tables escape the enumeration.** `prompt_grant`'s fields are
`prompt_id, grantee_user_id, level, granted_by, granted_at` — no `workspace_id`, so ADR-0035's CI test
does not see it. That is the same defect ADR-0040 found on `call_body` two decisions ago, on a table
with a stronger claim to the policy: `prompt_grant` is the mechanism by which BR-01's
*"prompts are private by default"* is implemented. `workspace` escapes for a different reason — it has
no `workspace_id` column because it **is** the workspace, and a policy on it must be written against
`id`.

Doing nothing about `api_key` is not neutral. `GET /api/v1/workspaces/{id}/keys` is a list endpoint
returning key names, scopes, `last_four` and `last_used_at`; a forgotten filter there is precisely the
silent cross-tenant read ADR-0035 exists to convert into zero rows.

## Decision

**Row-level security stays enabled on every table in the `access` schema that has a tenant column, and
the authentication bootstrap escapes it through exactly two `SECURITY DEFINER` functions.**

- `access.lookup_session(p_id text)` and `access.lookup_api_key(p_key_id text)` are owned by
  `prope_migrate`, declared `SECURITY DEFINER`, and therefore execute as the table owner, which bypasses
  the policy (ADR-0035, and the same ownership mechanic ADR-0037 relies on).
- **Each returns only the identity tuple** — `(user_id, workspace_id)` and
  `(workspace_id, key_id, key_hash, scope_model_names, revoked_at)` respectively. Neither returns a row
  set, neither takes a filter the caller composes, and neither can be made to return a second
  workspace's data by any argument. The hash comparison stays in the application (A-113), so the
  function is a lookup, not an authenticator.
- `REVOKE EXECUTE … FROM PUBLIC` then `GRANT EXECUTE … TO prope_app`, and both carry an empty
  `search_path` set on the function, so a `SECURITY DEFINER` body cannot be redirected by a caller's
  `search_path`.
- **Everything else keeps the policy.** `GET /workspaces/{id}/keys` reads `api_key` through the policy
  like any other list. The functions are used on exactly two code paths and both are on the
  authentication seam.
- **`prompt_grant` gains a `workspace_id` column** and a policy, so ADR-0035's CI test reaches it.
  `prompt_id` remains a value rather than a foreign key for the reason the lock already gives.
- **`workspace` gains a policy written against `id`**, and **ADR-0035's CI test gains a second clause**:
  a table is in scope if it carries `workspace_id` *or* is the `workspace` table itself. Without that
  clause the enumeration silently skips the tenancy root.
- **Workspace creation needs no function.** The application generates the identifier (A-045), so
  `POST /api/v1/workspaces` sets `SET LOCAL app.workspace_id` to the id it is about to insert, inside
  the same transaction that creates the row and its creator's Admin binding (A-109, A-117). The
  `WITH CHECK` half then passes on the row's own terms.
- The login read needs no function either: `access."user"` carries no tenant column and has no policy.

## Alternatives rejected

**Leave row-level security off `session` and `api_key`.** The argument for it is real — both are read by
an unguessable value, so the key is itself the authorization, and a policy adds little to a primary-key
read. It was rejected on the list endpoint and on the exemption. `api_key` is not only read by key; it
is enumerated by workspace on a management screen, and that path is exactly the one ADR-0035 was
written to protect. And the mechanism required is an **exemption list in the CI test** — the test whose
entire value is that it enumerates unconditionally. An exemption list is a place for the next table to
be quietly added by whoever finds the test inconvenient, which is the failure this project has now
declined four times (BR-03's constraint, ADR-0025's privilege, ADR-0027's schema, ADR-0035 itself).

**A permissive policy when the tenant context is unset** —
`USING (current_setting('app.workspace_id', true) IS NULL OR workspace_id = …)`. One line, no migration
objects, no functions. Rejected because it makes *"no tenant context"* a legitimate state that reads
every workspace, and ADR-0035's whole value is that a query path which forgets `SET LOCAL` returns zero
rows *loudly* instead of succeeding quietly. Under this policy the forgotten `SET LOCAL` succeeds and
returns everything. ADR-0040 rejected the identical construction for the ledger writer one decision ago
and named it: **a hole wearing a policy's clothes.** It would be inconsistent to accept it here, where
the tables are the tenancy root rather than a call log.

**A fourth database role that bypasses the policy for authentication.** Rejected on the same reasoning
ADR-0040 used against a `BYPASSRLS` ledger writer, and more strongly. It would make the credential used
on *every single request in the product* the one outside tenant isolation — the opposite of ADR-0037's
principle that each role's answer to *"what could this leak"* is different and narrow. It also needs a
second connection pool against ADR-0027's one, on the hot path.

## Consequences

- **The escape hatch is two functions with fixed signatures, and it is greppable.** Any future
  bypass of tenant isolation is either one of these two names or a new `SECURITY DEFINER` object, and
  a migration adding one is visible in review. Compare the rejected options, where the bypass is an
  absent policy or a role — neither of which appears at the call site at all.
- A test asserts that `access.lookup_session` and `access.lookup_api_key` are the **only**
  `SECURITY DEFINER` objects in the database, in the same shape as ADR-0025's privilege test and
  ADR-0035's policy test. This is the sibling AC-10 needs.
- `prompt_grant` gaining `workspace_id` denormalises a value that is derivable from the prompt — the
  same trade ADR-0040 made for `call_body`, for the same reason: a column the enumeration can see is
  worth more than a join that proves it redundant. The grant path already knows the workspace, because
  the caller supplied the subject (ADR-0020).
- **ADR-0035's CI test now has two clauses instead of one**, and the second exists solely for
  `workspace`. That is a wart, and it is a smaller one than a tenancy root with no policy.
- `SECURITY DEFINER` is a well-known footgun. The three standard mitigations are all applied and all
  testable: an empty `search_path`, `REVOKE … FROM PUBLIC`, and a return type narrow enough that the
  function cannot serve as a general-purpose reader.
- Nothing here weakens ADR-0022. These functions read live rows on every request exactly as the
  uncached design requires; a revoked key's `revoked_at` comes back in the same tuple and the refusal
  is the application's, on the next request, with no TTL.

> **The second clause is retired 2026-08-09 by ADR-0045.** The clause added above — *"a table is in
> scope if it carries `workspace_id` **or** is the `workspace` table itself"* — was a wart bolted onto
> the test's query, and it was the second consecutive pass to patch that test. The pass after this one
> found a third instance (`provider.credential`, holding every provider secret in Prope), at which point
> the rule inverted: the test now walks **every** table in the module schemas and requires each to be
> tenant-scoped or declared in `GLOBAL_TABLES` with a written reason. `access.workspace` becomes an
> ordinary entry in that map — *policied on `id`, not on `workspace_id`* — rather than a special case
> inside a query.
> **Everything else in this ADR is unchanged.** The two `SECURITY DEFINER` functions remain the only
> sanctioned bypass of the policy anywhere in Prope, `prompt_grant`'s new column stands, and the test
> asserting exactly two such objects exist is unaffected — ADR-0045 governs *which tables are checked*,
> this one governs *the two reads that must run before a tenant is known*.

> **Two becomes three, 2026-08-09, by ADR-0049 — the first addition since this ADR was written.**
> `evaluation.claim_next_run()` joins `access.lookup_session` and `access.lookup_api_key`. The
> justification is this ADR's own sentence, transplanted without alteration: **a queued eval run's
> workspace is not known until the claim, because the claim is what produces it.** `worker` polls
> `eval_run` across every workspace to find work, which deny-by-default RLS correctly returns zero rows
> for.
>
> It is built to this ADR's template rather than beside it — owned by `prope_migrate`, `SECURITY
> DEFINER`, empty `search_path`, `REVOKE … FROM PUBLIC` + `GRANT TO prope_app`, and a return type narrow
> enough that it cannot serve as a general reader: five identifiers, no prompt text, no eval case input,
> no model output. `worker` then issues `SET LOCAL app.workspace_id` from that tuple and runs everything
> afterwards — the revision read, the dispatch, the pricing, the `case_result` writes — under ordinary
> policy.
>
> **The test's expected set goes to three and stays enumerated**, which is the control this ADR relies
> on. Worth recording as a general observation rather than a one-off: **a background worker that must
> discover its own work across tenants needs exactly the escape an authentication bootstrap needs, for
> exactly the same reason.** `worker` gained its first such job in this pass and will gain more. Each one
> is a named function returning identifiers, added to the enumerated set — never a widened policy, never
> a `BYPASSRLS` role, and never a mode a process runs in.

> **Three becomes four, 2026-08-09, by ADR-0051 — and the addition came with a rule about shape.**
> `access.list_workspaces()` joins the set. The prediction one paragraph above held immediately:
> *"`worker` gained its first such job in this pass and will gain more."* It gained the second in the
> very next pass — release-control's review-task gauges and its pointer-reconciliation query, both of
> which must see every workspace at once and both of which deny-by-default RLS correctly answers with
> zero rows. The failure that made it worth finding is that a zero-row answer here is not an error: the
> `BreakGlassTaskOverdue` gauge would have read `0` forever, and break-glass would have lost the only
> control that keeps it exceptional, silently.
>
> **The new constraint is on the return type, and it is the general rule this set has been missing.**
> The obvious implementation was one purpose-built function per sweep, returning the sweep's rows. That
> was rejected, and the reason generalises to every future member of this set: **a function that returns
> tenant identifiers keeps every subsequent data read under RLS; a function that returns rows does not.**
> A row-returning bypass performs the actual read with the policy off, so a defect in the function body
> is a cross-tenant read with nothing behind it. `access.list_workspaces()` returns `SETOF text` and
> nothing else; the caller then issues `SET LOCAL app.workspace_id` per workspace and runs ordinary
> policied queries.
>
> **It is deliberately generic, so the set stops growing.** One enumerator serves every cross-tenant
> background job in Prope, present and future. That matters because the control this ADR relies on is a
> test asserting the set is *exactly* N — an assertion that means nothing once N tracks feature count
> rather than architecture. Read the three rules together: **owned by `prope_migrate` with an empty
> `search_path`, returning identifiers only, and generic wherever one function can serve many callers.**

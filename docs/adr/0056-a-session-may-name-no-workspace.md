# ADR-0056 — A session may name no workspace; the chooser is what a person sees while it does

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: user
**Module**: access-control (owns `session`, `workspace_member`, the chooser's routes)
**Related**: A-071, A-109, A-110, A-116, A-117, A-144, ADR-0022, ADR-0029, ADR-0035, ADR-0042,
ADR-0043, ADR-0045, ADR-0052, ADR-0053, ADR-0057, OQ-137

## Context

Until this ADR a session **had** to name a workspace: `access.session.workspace_id` was `NOT NULL`,
and `sessions.sign_in` refused anybody without an active membership with the same `401` a stranger
gets. Two consequences followed, and both were reported as the problem this change was asked to fix.

**Registration created a workspace, because it had to.** `POST /api/v1/auth/register` minted
`"<display_name>"` as a workspace with the person as its Admin, Owner and Reviewer — not because a
new account wants a workspace, but because a session could not exist without one. Somebody whose only
reason for signing up was to join a colleague got a junk workspace of their own, permanently.

**And there was no route to the colleague's.** Membership could only be created by an Admin already
inside a workspace (`POST /workspaces/{id}/members`, A-110), and that route creates the account too —
so a person who had already registered could not be added at all without their email being free. The
product had exactly one way in and it always went to a new, empty tenant.

OQ-137 raised the picker as an open question and proposed two mechanisms for switching: a session
that carries no tenant until one is chosen, or delete-and-reissue. This ADR takes both — they are
the same mechanism seen from two ends.

## Decision

**A session may name no workspace. That state is the lobby, and it is a first-class one.**

1. **`access.session.workspace_id` becomes nullable** (revision 0022). NULL is the lobby: the person
   is authenticated and is acting in no tenant.

2. **A second RLS policy carries it, rather than a weakened first one.** The base
   `session_tenant` policy is `workspace_id = current_setting('app.workspace_id', true)`, which is
   `NULL = NULL` — unknown — for a lobby row: invisible and un-INSERTable. So revision 0022 adds
   `session_lobby`, `FOR ALL`, `USING (workspace_id IS NULL AND user_id = current_setting('app.user_id', true))`.
   Postgres OR-s multiple policies for one role and command, so the exception is additive and the
   tenant predicate stays byte-identical to what `enable_tenant_rls` writes everywhere else.

   **A third `SECURITY DEFINER` function was the alternative and is refused.** ADR-0042's set is
   exactly four and a test asserts it; a fifth escape would have bought the same rows as one new GUC
   and one named policy, while making the sanctioned-escalation list an argument rather than a list.

3. **`app.user_id` is a new non-tenant GUC**, set by `db.session.lobby_transaction`. It authorises
   nothing on its own — every tenant-scoped table still answers to `app.workspace_id` alone — and the
   only policy that reads it is the one above.

4. **Entering a workspace deletes the session and issues another**, with a new cookie. This is not a
   preference: a cross-tenant `UPDATE session SET workspace_id` is impossible from both sides at once
   — the old tenant's `WITH CHECK` refuses the new value and the new tenant's `USING` cannot see the
   row. It is also OQ-137's own second proposal, and it means a switch leaves the same trail a
   sign-out and a sign-in would.

5. **Registration creates a person and nothing else.** No workspace, no membership, no role binding,
   no `workspace_created` event. `access."user"` is global (ADR-0045) and carries no policy, so the
   insert needs no tenant context at all — which is exactly the reach that function should have.

6. **Sign-in lands where the memberships say.** Exactly one active membership binds the session to
   it; none or several issue a lobby session and the SPA routes to the chooser. A person with no
   membership no longer gets the stranger's `401` — that answer was correct only while a session had
   to name a tenant, and it would now lock somebody out of the very screen that exists to give them
   one.

7. **Three routes are reachable from the lobby**, all `SELF_SCOPED`:
   `GET /api/v1/auth/workspaces`, `POST /api/v1/auth/workspaces/{workspace_id}/enter`, and
   `POST /api/v1/workspaces`. `POST /api/v1/auth/invites/redeem` joins them under ADR-0057.

   **`WORKSPACE_ENTER` deliberately checks no `Action`.** The authority to enter a workspace *is* an
   active membership in it, checked against the row itself; a member with zero role bindings is a
   legitimate state (A-110), so any permission gate here would refuse exactly the person an Admin has
   just approved and not yet assigned.

8. **The session boundary splits in two.** `require_actor` authenticates and answers an
   `ActorSession` whose `workspace_id` may be `None`; `require_session` additionally insists on a
   workspace and answers the unchanged `Session`, whose `workspace_id` is still a plain `str`. Every
   route that touches tenant data keeps the dependency it already declared, and
   `tests/architecture/test_route_table.py` accepts either as a declared boundary.

9. **A lobby session presented to a workspace route answers `403 workspace_required`**, not `401`.
   The person **is** signed in; a `401` would send the SPA to the sign-in screen, where signing in
   again would produce the same session and change nothing.

## Consequences

**A `NOT NULL` that documented an invariant is gone**, and what replaces it is a policy. A bug that
wrote NULL where a workspace was meant would previously have been refused by the engine and now
produces a session that quietly sees nothing. What bounds it: `issue_session` takes
`workspace_id: str | None` explicitly and picks its transaction from it, so there is one place the
choice is made rather than a default that can be forgotten.

**Two session-reading queries exist where there was one.** `LOAD_SESSION_ENVELOPE` joins the
workspace and the role bindings; `LOAD_LOBBY_SESSION_ENVELOPE` joins neither, because neither exists.
One query with outer joins was the alternative and is worse: its correctness would depend on which
GUC the caller happened to set, and getting that wrong renders as *"signed out"* to somebody who is
signed in.

**Sign-out now has two halves.** A session in a workspace is deleted under that tenant; lobby rows
are deleted under `lobby_transaction`. `logout` does both, and `remove_member`'s tenant-scoped delete
correctly leaves a removed person's lobby session alive — they are still a person, just not one of
this workspace's.

**A person can now hold several workspaces and switch between them**, which was not previously
expressible. Every consequence of that lands on the cookie: the SPA clears its whole query cache on
entering, because everything in it was read under the old tenant.

**A-110's clause that a workspace is the only way in is superseded in part.** The rest of A-110 —
Admin-created accounts, the handed-over password, `must_change_password` — is untouched, and the
change-password screen is deliberately reachable from a lobby session.

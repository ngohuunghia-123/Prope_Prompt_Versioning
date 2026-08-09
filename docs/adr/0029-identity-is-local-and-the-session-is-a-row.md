# ADR-0029 — Identity is local to Prope, and the session is a row

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: access-control — cited by every module that authenticates a human actor
**Related**: A-020, A-071, A-081, A-108, A-110, A-113, A-114, ADR-0021, ADR-0022, ADR-0034, OQ-006

## Context

`module_map.md` names this as the single unestimated half of access-control:

> "What is unestimated is a different half of the same question — **whether the pilot must authenticate
> against the group's identity provider**. A-108 assumes local email and password with server-side
> sessions, and if that is wrong the work is an OIDC integration nobody has scoped."

A-108 recorded that assumption as `decided_by: agent` and flagged itself as *"the default most worth
overturning early, because the cost of the answer arriving late is larger than the cost of either
answer."* Step 4 is where that answer is due.

Two identity surfaces exist and only one is in question. Machine callers use Prope's own consumer API
keys — `prope_<key_id>_<secret>`, stored as a fast hash, shown once, default-deny, naming the model
names they may resolve (A-113, A-081, ADR-0021). No identity provider touches that in any option; the
gateway holds no key material and a scope refusal returns the same not-found shape as an unknown model
name. This ADR concerns **how a human signs in**.

One interaction constrains every option. ADR-0022 makes revocation effective on the next request, and it
gets that property from server-side session rows: sign-out and member removal end a session immediately.
The conventional OIDC shape — a self-contained token the application validates offline — would break
that silently, leaving a removed member working until their token expired. Any federated option must
therefore still mint a local session after the callback, using the token only to establish identity once.

## Decision

**A human authenticates with an email address and a password stored as an argon2id hash, and receives a
server-side `session` row referenced by an HTTP-only cookie. There is no OIDC, no SAML, and no social
sign-in in the MVP. A-108 is confirmed and its `decided_by` becomes `human`.**

- The cookie is `HttpOnly`, `Secure`, `SameSite=Lax`, and **same-origin** with the API. ~~ADR-0034 makes
  the UI server-rendered from the same FastAPI application and~~ ADR-0033 puts one Caddy origin in front
  of everything, so there is no cross-origin case and no CORS configuration to get wrong.
  *Amended 2026-08-09* — ADR-0052 replaced the server-rendered UI with a React SPA, and **every clause of
  this bullet survives unchanged**, because what made it true was the shared **origin**, not the shared
  process. Caddy serves the SPA from `/` and proxies `/api/*` and `/v1/*` to `app` (A-129, ADR-0052), so
  the cookie is still same-origin, there is still no CORS, and there is still no token forwarding. Worth
  stating explicitly since this is where a React frontend would normally break a session design: **no JWT
  is introduced, and no CSRF token is added** — `SameSite=Lax` already withholds the cookie from a
  cross-site `POST`, and a same-origin `fetch` from the SPA carries it. This bullet was the reason ADR-0052
  rejected a separate Node origin.
- **Credential verification is a separate function from session minting.** This is one function
  boundary, deliberately not a plugin architecture: the point is that adding an OIDC callback later
  means adding a second way to reach `mint_session(user_id)`, not restructuring the session, permission,
  or revocation machinery.
- Login is rate-limited per email address and per source address, and the response for an unknown email
  is identical to the response for a wrong password.
- Passwords are never returned by any read API and never appear in a log line, a metric label, or a
  history event. Sign-ins and failed sign-ins are deliberately **not** history events — property history
  is the log of state changes, and authentication traffic belongs in metrics and logs (A-044).
- argon2id parameters are chosen for a deliberate CPU and memory cost. That cost is the point, and it
  lands on the same process as the gateway; A-130 records the split trigger that bounds the consequence.

## Alternatives rejected

**OIDC against the group's identity provider.** Rejected for the MVP on scope, not on merit — and it is
the alternative most likely to return. Three facts point the same way today. A-020 already bars real
corporate prompts from the pilot until the security baseline is signed off, so there is no corporate
identity in scope to federate. A-110's flow — *"a person joins a workspace by an Admin creating the
account; there are no invitations, because there is no email"* — is only coherent without an identity
provider, since an IdP would normally provision on first login. And the work is genuinely unscoped:
discovery, callback handling, JIT provisioning, and ownership of an application registration inside the
group. If a policy requires federated sign-in, this ADR is superseded rather than amended, and OQ-006
moves from `narrowed` to a sized work item.

**Self-hosted Keycloak.** Rejected as paying both costs. It removes the dependency on the group's IdP
team but still requires the entire OIDC integration to be built, *and* adds a service with its own
database, upgrade path, and unseal-equivalent operational knowledge to a VM already running seven
things. Against a live host compromise it protects nothing that a local `user` table does not.

**Self-contained JWTs with no server-side session.** Rejected because it contradicts ADR-0022 directly.
A stateless token is a cached authorisation decision with no invalidation path, and A-114 states that
nothing in access-control is cached *"by this module or by its callers"* precisely so that a revoked
key or a removed member stops working on the next request. Accepting JWTs would mean accepting that
member removal takes effect at token expiry, which is the failure ADR-0022 was written to prevent.

**Magic links.** Rejected by A-071: *"no email and no Slack in the MVP; the in-app review queue is the
whole notification surface."* A magic link is an email product.

## Consequences

- A-108 is confirmed by a human and its status changes accordingly. OQ-006 narrows again: its
  identity-provider half is now answered, leaving **data classification** as the only open element.
- Account creation stays an Admin action (A-110). There is no self-service signup, which is a scoping
  consequence worth naming — it is the first thing that would have to change if Prope became a product
  sold to strangers rather than deployed inside one group.
- The `user`, `session`, `workspace_member`, `role_binding` and `role_permission` tables live in the
  `access` schema (ADR-0027) and are subject to ADR-0035's tenant policy like everything else.
- Adding OIDC later is additive against the same `user` row, exactly as A-108 predicted, and the local
  password path can then be disabled per workspace without touching sessions or permissions.

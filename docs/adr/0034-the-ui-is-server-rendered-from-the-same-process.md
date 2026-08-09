# ADR-0034 — The UI is server-rendered from the same process, and there is no Node

**Status**: **Superseded by [ADR-0052](0052-the-ui-is-a-react-spa-built-in-ci-and-served-by-caddy.md),
2026-08-09** — the same day it was accepted.
**Date**: 2026-08-09
**Decision**: user

> **Superseded, 2026-08-09.** The user chose React for ecosystem compatibility. ADR-0052 takes the
> alternative this ADR named as *"the natural upgrade"* — a Vite + React SPA — with Node in CI only and
> the assets baked into a Caddy image, so the service count and the same-origin cookie both survive.
>
> **Read this ADR for what it still gets right.** Two of its three load-bearing claims are carried into
> ADR-0052 unchanged: that Node must not run in production on a 4 vCPU host maintained by nobody in
> particular, and that the same-origin cookie is what keeps ADR-0022 and ADR-0029 simple. What it lost is
> the third — that a JSON boundary between renderer and service is *"pure cost"* for screens that are
> *"lists, forms, a table and a diff"*. That was an argument about the screens, and the user's decision is
> about the toolchain around them.
>
> **Its reversal triggers were the useful part of the record.** It named two, and one fired: *"[the SPA]
> remains the natural upgrade if the UI later needs genuine client-side state that HTMX makes awkward."*
> The other — *"if OQ-005 answers that there is a dedicated frontend developer"* — **did not fire and is
> still open.** The reversal was taken ahead of the input this ADR nominated to settle it, which ADR-0052
> records as an accepted cost rather than hiding.
>
> One consequence below is **withdrawn** rather than superseded: *"because rendering shares a process with
> the gateway, ADR-0030's p95 histogram now measures the consequence of a UI decision as well as a gateway
> one."* It no longer does. Jinja leaves `app` entirely, which shortens A-130's cost list from three
> items to two — see ADR-0052's consequences.
**Module**: global — the UI is not a module; it renders screens owned by four of them
**Related**: A-015, A-018, A-045, A-047, A-050, A-054, A-071, A-129, A-130, ADR-0022, ADR-0026,
ADR-0029, ADR-0033, OQ-005

## Context

`module_map.md` deliberately has no frontend module: *"Do not produce horizontal layers — 'frontend',
'backend', 'data layer' are deployment concerns, not modules."* But prompt-registry, release-control,
evaluation and provider-access all describe screens, and those screens ship in one application. That
makes the UI runtime a global baseline concern that the seven-concern list did not contain. Left
unasked, `tech_stack.md` would lock with nothing to build the review screen from.

`00_context.md#constraints` names Next.js in the inherited stack row. The repository contains **no
`package.json`**, so this is an intention rather than an inheritance.

What the UI actually has to do, read off the locks: a filterable registry list; a side-by-side revision
diff, which A-015 fixes as *"a line-level textual diff, not a consequence-language diff"* and A-047
computes on demand and never stores; an eval results table with per-case pass/fail and a cost delta; a
review screen carrying approve and request-changes; provider configuration forms; and an Activity feed
backed by A-119's single indexed read. That is forms, lists, a table, and one diff.

**There is no realtime surface anywhere in the MVP.** A-071 makes *"the in-app review queue the whole
notification surface"* with no email, Slack or webhook, and A-054 has the eval client **poll**. Nothing
in scope streams to a browser.

## Decision

**Jinja2 templates with HTMX and Tailwind, rendered by the same FastAPI application. No Node in
production and none at build time — Tailwind 4 ships a standalone binary.**

- **One service layer, two renderers.** A-045 specifies a JSON management API — ULID identifiers, one
  error envelope, cursor pagination, `/healthz` and `/readyz`. With HTMX, screens call handlers that
  return HTML fragments, so nothing in Prope consumes that JSON. The same service function therefore
  backs both `GET /api/v1/prompts` and the fragment the list screen swaps in. A-045 stays true and
  neither surface becomes the other's afterthought — which is the failure mode this decision would
  otherwise create.
- **The session story is the simplest available.** ADR-0029's cookie is same-origin with the API, so
  there is no CORS configuration, no token forwarding, and no per-route decision about which side holds
  the session. ADR-0022's immediate revocation is preserved without special handling.
- Caddy (A-129, ADR-0033) serves static assets and terminates TLS; every dynamic path reaches FastAPI.
- **A-018 governs copy**: Vietnamese UI text with English status labels and API vocabulary. Statuses
  render literally — Draft, In review, Approved, In use, Retired — and the mandated user-facing
  vocabulary applies throughout: revision, restore, release, grant access, never version, rollback,
  promote, publish or share.
- **The diff is the one CPU-shaped screen.** A-050 caps a prompt body at 32 KiB, so a side-by-side line
  diff of two revisions is real computation on the event loop it shares with the gateway. A-130 records
  the split trigger and the histogram that fires it.

## Alternatives rejected

**Next.js with TypeScript, per the constraints row.** Rejected after being chosen and reconsidered, on
the grounds that every core feature it sells is either irrelevant here or duplicates a decision already
made. Server rendering for SEO and first paint has no value in a private authenticated tool with no
public page and no crawler. React Server Components would make Node call FastAPI server-side — a second
hop and a second place session cookies must be forwarded correctly. Its route handlers would be a second
backend nobody wants, since the API is FastAPI. Image optimisation has no images to optimise. And it
requires a **Node process in production**: an extra service, an extra runtime, an extra CI lane and an
extra dependency-vulnerability surface, all maintained by whoever maintains the Python side. The
condition that would reverse this is a person rather than a feature — **if OQ-005 answers that there is
a dedicated frontend developer**, familiarity outweighs architectural tidiness and this ADR is
superseded.

**A Vite + React single-page application served as static files by Caddy.** Rejected as the better of
the two JavaScript options and still worse than the decision. It removes Node from production entirely —
the bundle is static — and keeps the same-origin cookie story intact, so it costs one container less
than Next.js and shares most of this ADR's advantages. What it does not remove is the second language,
the second toolchain, the build lane, and the duplication of every view model across a JSON boundary
that exists solely because the renderer lives in a different runtime. For screens that are lists, forms,
a table and a diff, that boundary is pure cost. It remains the natural upgrade if the UI later needs
genuine client-side state that HTMX makes awkward.

## Consequences

- The service count stays at seven (ADR-0033). There is no `web` container, no second image, and no
  frontend build in CI beyond a Tailwind invocation.
- The JSON management API is built for external and programmatic consumers rather than for Prope's own
  screens. It must therefore be tested on its own terms — a contract test, not a by-product of the UI
  working.
- HTMX's ceiling is real and this is the honest limit of the decision: a screen that needs rich
  client-side state will be awkward. Nothing currently specified needs one, and A-054's polling and
  A-071's in-app queue are what keep that true.
- The UI is not a module and therefore has no lock file. Its screens belong to the modules that own the
  data behind them, and each module's per-module pass records its own view rows.
- Because rendering shares a process with the gateway, ADR-0030's p95 histogram now measures the
  consequence of a UI decision as well as a gateway one. That is deliberate: it makes A-130's trigger a
  number rather than a suspicion.

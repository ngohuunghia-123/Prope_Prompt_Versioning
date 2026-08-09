# ADR-0052 — The UI is a React SPA built in CI and served by Caddy; Node never runs in production

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — the UI is still not a module; it renders screens owned by four of them
**Supersedes**: ADR-0034
**Related**: A-012, A-015, A-018, A-045, A-047, A-050, A-054, A-071, A-113, A-129, A-130, A-141,
ADR-0003, ADR-0022, ADR-0026, ADR-0029, ADR-0031, ADR-0033, ADR-0043, ADR-0046, ADR-0049, ADR-0050,
OQ-005, `00_context.md#constraints`

## Context

ADR-0034 chose Jinja2 + HTMX + Tailwind rendered by the same FastAPI process, with **no Node in
production and none at build time**. It was the right shape for the screens as specified — *"forms,
lists, a table, and one diff"* — and it wrote down the two conditions that would reverse it. Both are
worth quoting, because one of them fired and the other did not:

> "The condition that would reverse this is a person rather than a feature — **if OQ-005 answers that
> there is a dedicated frontend developer**, familiarity outweighs architectural tidiness and this ADR is
> superseded."

> "[A Vite + React SPA] **remains the natural upgrade if the UI later needs genuine client-side state
> that HTMX makes awkward.**"

**The user asked for React, for ecosystem compatibility, on 2026-08-09.** `00_context.md#constraints`
also names Next.js in the inherited stack row, which ADR-0034 correctly discounted as an intention rather
than an inheritance — the repository still contains no `package.json` — but the intention was real and
this decision meets it.

**OQ-005 remains unanswered.** There is no deadline and no team size on record. That is stated here
rather than glossed: this reversal is a product-owner call taken *ahead of* the input ADR-0034 nominated
to settle it, and A-012's *"small team, no dedicated ops"* now carries a second language and a second
toolchain. That is an accepted cost, recorded in the consequences below and not argued against.

What did **not** change is the shape of the screens or the absence of a realtime surface: A-071 still
makes the in-app queue the whole notification mechanism and A-054 still polls. So this ADR is about
runtime and packaging, not about a new capability the old stack could not serve.

## Decision

**A React + TypeScript single-page application, built with Vite, styled with Tailwind 4 as an npm
dependency. Node runs in CI only. The build emits static assets baked into a second image derived from
`caddy:2`, and Caddy serves them on the same origin as the API.**

```dockerfile
# image 2 of 2 — prope-web
FROM node:22-alpine AS build
WORKDIR /src
COPY web/package*.json ./
RUN npm ci
COPY web/ .
RUN npm run build          # vite build → /src/dist

FROM caddy:2
COPY --from=build /src/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
```

```caddyfile
prope.example.internal {
    handle /v1/*   { reverse_proxy app:8000 }   # ADR-0050's gateway app
    handle /api/*  { reverse_proxy app:8000 }   # ADR-0003's management API
    handle /metrics { reverse_proxy app:8000 }
    handle {
        root * /srv
        try_files {path} /index.html            # SPA fallback
        file_server
    }
}
```

- **Node never runs in production.** The service count stays at **seven** (ADR-0033). There is no `web`
  container and no Node process to keep alive, patch, or debug at 3am — which is the half of ADR-0034's
  argument that survives its own reversal intact.
- **The routing separation is structural, not an ordering rule.** Caddy dispatches on path prefix in
  configuration. The rejected alternative — `StaticFiles` plus a catch-all SPA fallback inside FastAPI —
  requires that fallback to be registered *after* the API routers and after
  `management.mount("/v1", gateway)`, or the OpenAI-compatible surface starts returning `index.html` to a
  consumer's SDK. This build has declined an application-maintained invariant of that shape nine times;
  ADR-0050 declined this exact one, in this exact process, one pass ago.
- **The same-origin cookie is preserved, and so is everything resting on it.** One origin, served by
  Caddy (A-129), so ADR-0029's `HttpOnly` `Secure` `SameSite=Lax` cookie and its server-side session rows
  are untouched, ADR-0022's revocation-on-next-request is untouched, and **no JWT and no CORS
  configuration enters the system**. `SameSite=Lax` already blocks cross-site `POST` from carrying the
  cookie, so **no CSRF token is added either** — the mechanism that made ADR-0034's session story simple
  was the shared origin, not the shared process.
- **Tailwind moves from the standalone binary to `tailwindcss` + `@tailwindcss/vite`.** ADR-0034 used the
  binary specifically to keep Node out of the build; with a Node build stage that reason is gone and the
  ordinary integration is simpler.
- **The JSON API becomes the only API.** Under HTMX, handlers returned HTML fragments and *"nothing in
  Prope consumes that JSON" —* A-045's management API was built for external consumers alone. The SPA now
  consumes it, so ADR-0003's envelope, ULID identifiers and cursor pagination have a first-party client.
  There is one surface where there were two shapes.
- **A-018 governs copy unchanged**: Vietnamese UI text, English status labels rendered literally — Draft,
  In review, Approved, In use, Retired — and the mandated vocabulary throughout: revision, restore,
  release, grant access.
- **CI publishes two images** (ADR-0031): `prope-app` and `prope-web`. The deploy pulls two tags; the host
  still never builds.

## Alternatives rejected

**Next.js with a Node server in production.** The option `00_context.md#constraints` originally named,
and rejected again here on the same grounds ADR-0034 used, which the move to React does not disturb:
*"every core feature it sells is either irrelevant here or duplicates a decision already made"* — no SEO
surface in a private authenticated tool, RSC would make Node call FastAPI server-side and add a second
place session cookies must be forwarded correctly, its route handlers would be a second backend beside
FastAPI, and there are no images to optimise. What it adds beyond that is an **eighth container on
ADR-0033's 4 vCPU / 8 GB VM**, a second runtime to patch, and a second dependency-vulnerability surface —
against A-012's *"small team, no dedicated ops"*, which is the constraint the whole deployment is shaped
around. The request was React compatibility; a Node runtime in production is not part of it.

**React via ESM and import maps, with no build step at all.** Keeps ADR-0034's *"no Node, production or
build"* literally true and still gives the component model. Rejected because it forfeits the thing that
motivated the request: no TypeScript compilation, no bundler-assuming component libraries, no npm
dependency tree. It would satisfy the letter of "use React" and none of the intent.

**Serve the built assets from FastAPI via `StaticFiles`.** One image, one tag, the simplest deploy
script — genuinely the friendliest option for *"one `docker-compose up`"*. Rejected on the route-ordering
hazard described in the Decision: a catch-all registered in the wrong place silently converts the one
surface `00_context.md#constraints` makes non-negotiably wire-compatible — *"the gateway must be
wire-compatible with the OpenAI chat-completions request and response shape"* — into an HTML page, with
nothing in CI to catch it. It also puts static bytes through the process holding the only Success-metric
latency budget in the build.

**Assets in a named volume populated at deploy time.** Stock Caddy, one app image, no static serving in
Python. Rejected because the UI and the API then version independently: a rollback of `prope-app` leaves
the previous deploy's SPA calling the current API, and ADR-0031's *"the tested artefact is the deployed
one"* stops being true for the frontend. Recovering it means version-stamping the volume, which is a
build system written in shell.

## Consequences

### Jinja leaves `app`, and that deletes a premise from three live arguments

This is the substantive architectural consequence, and it runs opposite to the usual direction: a new
decision **removing** a premise from arguments already on record, caught in the same pass rather than
four passes later.

Three places name the same two in-process CPU competitors for the gateway's p95:

- **ADR-0046**: *"A-130 records the same class of coupling for **argon2id and Jinja rendering**. Separate
  containers remove all of it at once."*
- **ADR-0049**: *"…the process holding the gateway's p95 budget, **alongside argon2id and Jinja
  rendering** (A-130)."*
- **A-130** itself: *"**Jinja rendering of a long list is synchronous work**."*

Rendering now happens in the browser and `app` returns JSON. **A-130's cost list drops from three items
to two**, and its trigger gets *weaker*.

**What remains, precisely** — this matters, because the obvious overstatement is that the split argument
collapses entirely, and it does not:

| A-130's CPU competitor | After ADR-0052 |
|---|---|
| A-047's diff over 32 KiB bodies | **Stays in `app`.** prompt-registry computes it with `difflib` and `SequenceMatcher(autojunk=False)` and returns structured data; only the *painting* of it moves to the browser. AC-2 still asserts 300 ms at the cap |
| Jinja rendering of a long list | **Gone.** The list is JSON; the browser lays it out |
| argon2id at `m=47104` · `t=1` · `p=1` | **Stays**, and ADR-0043 sized `p=1` *because of* this co-tenancy |

So the split still has a real case — the diff and the login hash — and it has lost the one item that
scaled with screen size rather than with a bounded input. ADR-0046, ADR-0049 and A-130 are all amended to
say two where they said two-plus-Jinja.

ADR-0034's closing consequence is also withdrawn — *"because rendering shares a process with the gateway,
ADR-0030's p95 histogram now measures the consequence of a UI decision as well as a gateway one"*. It no
longer does, which makes that histogram a cleaner instrument, not a poorer one.

### The rest

- **The UI is still not a module and still has no lock file.** Its screens belong to the modules that own
  the data behind them. **No module lock's `language_runtime`, `deployment_target` or
  `libraries_frameworks` changes** — every per-module stack row survives this reversal untouched, which is
  the test of whether ADR-0034 put the concern in the right tier.
- **A second language and toolchain now exist**, against an unanswered OQ-005. `npm audit` joins the CI
  job, and the dependency surface that ADR-0034 declined arrives with the ecosystem that was asked for.
  This is the cost, stated plainly.
- **The diff is now a client-side render of server-computed data.** prompt-registry still computes it with
  `difflib` and `SequenceMatcher(autojunk=False)`; A-015's *"line-level textual diff"* and A-047's
  compute-on-demand-never-store are both unaffected. What moves is the painting of it, and it moves off
  the event loop the gateway shares.
- **A-141 records a failure mode server rendering made impossible**: the SPA is Prope's first long-lived
  client of its own API, so a browser tab open across a deploy runs the previous build's JavaScript
  against the new API.
- **ADR-0026 loses one supporting sentence and keeps its decision.** Its rejection of *"Node/TypeScript
  for the whole system"* cited ADR-0034's absence of Node as support; that support is gone and the
  rejection now stands on the half that was always load-bearing — Python is *"the only genuinely
  inherited, working part of the stack."* A JavaScript build lane is not an argument for rewriting eight
  Python modules.
- **ADR-0033's service table is amended**: `app` is *"FastAPI — management API and gateway"*, and `caddy`
  becomes a **built image rather than a stock one**. Seven services, two images.
- **The management API must still be tested on its own terms.** ADR-0034 warned that a UI-coupled API
  becomes a by-product of the screens working; that risk *inverts* rather than disappears — the API now
  has a first-party consumer, so its contract test matters for the opposite reason: an external SDK must
  see the same shape the SPA does.

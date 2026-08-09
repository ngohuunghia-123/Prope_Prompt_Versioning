# ADR-0050 — The gateway is a mounted sub-application with its own error contract

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: gateway — the one surface exempt from ADR-0003's error envelope
**Related**: A-026, A-031, A-045, A-046, A-081, A-113, A-114, A-116, A-129, A-130, ADR-0003, ADR-0011,
ADR-0012, ADR-0021, ADR-0022, ADR-0026, ADR-0033, ADR-0034, ADR-0043, ADR-0046, OQ-012

## Context

The gateway is the only surface in Prope that does not speak Prope's own API conventions. A-045 grants
the exemption and A-026 says what replaces it: the OpenAI request, response and **error** shapes, wire
compatible, *"never the management envelope"*. A-116 goes further and makes the error contract carry a
security property — *"a scope refusal returns the same not-found shape as an unknown model name"* —
asserted by AC-10.

A-130 puts that surface in the same process as the management API and the server-rendered UI for the
pilot. **Starlette registers exception handlers per application object, not per route**, so one
`FastAPI()` instance serving both surfaces has exactly one set of handlers and one default for every
error the framework raises before user code runs.

That matters because the module's own top risk is this:

> *"Wire compatibility is asserted, not achieved — a near-miss in the streaming format, the error body,
> or a field's type breaks every consumer's SDK at once. This is the reason the map scores gateway
> `Estimable: no`."*

The error body is one of the three things named, and it is the one that framework defaults control
rather than application code.

## Decision

**The gateway is a separate ASGI application object with its own exception handlers, its own middleware
stack and its own OpenAPI schema. The management application mounts it.**

```python
management = FastAPI()                      # ADR-0003's envelope, A-045's conventions
gateway    = FastAPI()                      # OpenAI wire format, A-026

gateway.add_exception_handler(RequestValidationError, openai_shaped)
gateway.add_exception_handler(StarletteHTTPException, openai_shaped)
gateway.add_exception_handler(Exception,              openai_shaped)

management.mount("/v1", gateway)
```

- **Isolation is structural, not conditional.** A `Mount` does not share exception handlers with its
  parent, so a 422 from request validation, a 405 from a wrong method, and an unhandled 500 all resolve
  inside whichever application owns the route. No handler inspects `request.url.path` to decide which
  contract it is serving, and no future handler has to remember to.
- **The three errors framework defaults own are the three most likely to reach a stranger.** A 422 is
  what a consumer hits first when integrating — the same position AC-7's rejected system message
  occupies, which the lock calls *"the single most likely first-integration mistake"*. A 500 is the
  least-tested path in the module and reaches the most external caller.
- **A-116's indistinguishability becomes enforceable in one place.** Unknown model, no release, and
  scope refusal all resolve through the gateway app's own handler set, so the identical-shape property
  is a property of that handler rather than of every call site remembering it.
- **`/healthz` and `/readyz` stay on the management application while the gateway lives in `app`.** The
  gateway lock's own readiness condition is *"access-control and prompt-registry are reachable"*, and
  ADR-0026 makes both in-process function calls — so that sentence **is** *"the database is reachable"*,
  which is exactly what ADR-0041 already has `/readyz` report. Two pairs would be two names for one
  fact. They separate again on an A-130 split, where the gateway app object needs its own.
- **The management application's `/docs` does not list `/v1` routes and vice versa.** Two schemas, which
  is correct: the OpenAI surface is documented by OpenAI's specification, not by ours.

### This restores A-130's stated price

A-130 says the split is *"one compose block from the same image… with no code change."* Locking the
gateway's stack made that inaccurate — ADR-0046's `interactive_concurrency` is a process-local
semaphore, and moving the gateway out leaves A-090's provider verification probe dispatching from `app`
with no cap, so the split costs a third column and an ADR-0046 amendment.

**This decision restores the other half.** Because the gateway is already a standalone application
object rather than a router on a shared one, the split is `uvicorn prope.gateway:app` against the same
image and a Caddy route — no code change, as A-130 claimed. The residual cost is ADR-0046's column
alone, and A-130 is amended to say exactly that rather than to claim the split is free.

## Alternatives rejected

**One application, route-scoped exception handlers** that inspect `request.url.path` and choose a shape.
Fewer moving parts, one middleware stack, one OpenAPI document — genuinely simpler, and it was the
obvious first answer. Rejected because it turns a contract boundary into a runtime string comparison
that every handler must repeat: `RequestValidationError`, `HTTPException`, `StarletteHTTPException`,
`Exception`, and each one added later. Forgetting it in any of them produces a **wrong error body on the
500 path**, which is the least-exercised code in the module reaching the most external consumer, and it
fails silently — Prope's own tests would pass, because Prope is not the thing that breaks. This project
has declined application-maintained invariants of exactly this shape seven times now (BR-03's
constraint, ADR-0025's privilege, ADR-0027's schema, ADR-0035's policy, ADR-0045's coverage test,
ADR-0048's trigger, ADR-0049's claim transaction).

**One application, gateway paths return pre-shaped `JSONResponse` objects** and never rely on handlers
at all. Most direct for everything the gateway explicitly knows about — auth failure, unknown model, no
release, pin-not-approved, scope refusal, missing variable, system-message refusal, upstream error
translation — and that list is most of the module's error surface. Rejected because the errors it cannot
reach are the ones that matter: a 422 from request validation, a 405, and any unhandled exception never
enter gateway code, so they exit through the shared handlers in the management envelope regardless of
how carefully the gateway's own returns are written. It covers the paths that are already tested and
misses the paths that are not.

**Run the gateway as its own container now**, which makes the isolation a process boundary and needs no
mounting decision at all. Rejected by A-130 in Q2 of this pass rather than here: the budget the split
protects is A-031's placeholder, OQ-012 has supplied no load figure, no load test exists to pull
A-130's stated trigger, and it spends an eighth service against A-012 plus ADR-0046's third column. This
ADR is what makes that decision cheap to revisit.

## Consequences

- **The contract test gets a target it can actually drive.** `test_plan.contract` says OpenAI
  compatibility is asserted *"by driving a real OpenAI client SDK, not hand-built JSON"*. The gateway
  application can be instantiated and driven standalone in tests, without the management surface, so
  what the SDK exercises is exactly what a consumer reaches.
- **Two acceptance criteria are owed**, recorded to the step-6 sweep: that a malformed request body on
  `/v1/chat/completions` returns an OpenAI-shaped 422 and never `{"detail": [...]}`; and that an
  unhandled exception raised inside a gateway route returns an OpenAI-shaped 500 carrying no management
  envelope field and no internal detail. Both assert the shape of a *failure*, which is the half of wire
  compatibility that ordinarily goes untested.
- **Middleware is now scoped and must be placed deliberately.** Anything registered on the management
  application runs outside the mount and therefore also for gateway requests; anything on the gateway
  application runs only for it. Request-logging middleware belongs on the gateway app, because A-046's
  never-logged list — *"the caller's messages, the response content… and the VALUES in
  `prope.variables`"* — is specific to this surface.
- **There is no runtime cost.** A `Mount` is a routing-table entry resolved once per request; the 50 ms
  budget is untouched.
- A future third contract — a webhook receiver, an admin surface with different auth — gets its own
  application object rather than a fourth branch in a shared handler. The pattern is now written down.

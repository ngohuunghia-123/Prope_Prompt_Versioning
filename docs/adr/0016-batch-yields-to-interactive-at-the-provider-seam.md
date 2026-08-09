# ADR-0016 — One key, two classes of traffic: batch yields to interactive

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-093)
**Module**: provider-access, evaluation, gateway (written while locking provider-access)
**Related**: A-029, A-043, A-062, A-063, A-084, ADR-0006, OQ-004, OQ-012

## Context

OQ-004's answer put one credential per provider configuration, paid for by the workspace, and gave
that same credential to both kinds of traffic Prope generates:

- **Interactive** — gateway calls on a consuming product's request path. A hard dependency
  (`00_context.md#constraints`), a 50 ms added-latency budget, and a human waiting.
- **Batch** — eval runs. ADR-0006 made suites named and independent, so one submit runs *every*
  suite the prompt has, and A-062's five-suite prompt means five runs of 10–20 cases, doubled
  whenever the baseline is not reusable (ADR-0004).

A provider's rate limit applies to the account, not to the caller's intent. So a reviewer clicking
"submit" can burn the same quota the checkout page's AI feature is using, and the provider answers
both with 429.

Nothing in the module map covers this. A-063 puts a global concurrency bound inside evaluation, which
is the right bound in the wrong place: evaluation cannot see gateway load, so it can only be
conservative in the abstract. The gateway has no knob at all. And the failure this produces is
precisely the one `positioning.md` §11 identifies as fatal — the developer persona experiences an
internal tool's batch job as a production incident, and vetoes.

## Decision

**Every dispatch declares a priority class, and admission at the provider seam favours interactive.**

- `dispatch(..., priority)` takes `interactive` (gateway) or `batch` (evaluation). It is a scheduling
  input, not a dependency — provider-access still knows nothing about either module.
- Each `provider_config` carries `max_concurrency` (default 32) and `reserved_interactive`
  (default `max(4, 25% of max_concurrency)`).
- **Batch dispatches may occupy at most `max_concurrency - reserved_interactive` slots.** The reserve
  is a floor for interactive traffic, not a cap on it: when the gateway is idle, batch may use the
  whole budget.
- **Interactive dispatches never queue behind batch.** If interactive cannot be admitted immediately
  it fails fast with `rate_limited{origin=prope}` rather than waiting — on a path with a 50 ms
  budget, a queue is a slower error, and the gateway has a fallback answer to serve.
- **On a provider 429, batch admission halves for a cooldown; interactive is untouched.**
- Every error carries `origin = prope | provider` (A-095), so "the provider throttled us" and "Prope
  shed us" are never the same number.

The mechanism is a per-configuration semaphore with a reserved share. It is not a scheduler, and it
is deliberately small.

## Alternatives rejected

**Do nothing; let both classes contend.** Rejected. It is the default that produces the exact
incident the positioning document names as the developer veto, and it produces it at the worst
moment — when a team is actively reviewing, which is when Prope is most visibly in use. "The eval run
took down checkout" is a sentence that ends a pilot.

**Separate credentials per purpose — one for traffic, one for evals.** Rejected on two grounds. It
doubles the BYOK setup burden against a user answer that was explicitly "toàn quyền kiểm soát trên 1
dashboard", and it mostly does not work: provider quotas are usually per *account*, so two keys share
one ceiling and the isolation is imaginary. It also creates a second credential to rotate, store, and
leak.

**Keep the bound only in evaluation (A-063).** Rejected as the wrong vantage point, not the wrong
idea. A-063 stays and still applies — it caps how much concurrency one workspace's runs may ask
for. What it cannot do is see live traffic, so its number has to be pessimistic enough to be safe
during a spike, which means it is wasteful the rest of the time. The seam that sees both classes is
this one.

**A fair-share queue across both classes.** Rejected because fairness is the wrong goal here. Fair
sharing adds wait to the interactive path in order to be equitable to a batch job that no human is
watching, which inverts the priority the product actually has. The asymmetry is the point.

**Rate-limit gateway traffic instead, to leave headroom for evals.** Rejected against a non-negotiable
row: spend ceilings "refuse eval runs, never gateway traffic" (A-029), and the same logic holds for
concurrency. Refusing production to protect a background job is the worse failure in every direction.

**Retry batch dispatches on 429 inside provider-access.** Rejected: A-088 keeps this module to
exactly one attempt so that A-084 (gateway never retries) and A-053 (evaluation retries transport
errors only) can both be true. Shedding early and telling the caller why is what lets evaluation's own
retry loop make an informed decision.

## Consequences

- A new failure mode exists that did not before: Prope's own ceiling can shed live traffic if
  `max_concurrency` is set too low. It gets its own counter and its own page
  (`ProviderInteractiveShed`), because the alternative is call records that blame the provider for a
  limit Prope set. This is the cost of the decision and it is stated rather than discovered.
- Eval runs get slower when live traffic is heavy. That is the intended direction, and
  `ProviderBatchStarved` warns — rather than pages — when it is sustained, because a reviewer whose
  screen never fills in deserves an explanation even when the system is behaving as designed.
- `priority` is on the dispatch contract from day one. Adding it later means changing an interface two
  modules already build against.
- The defaults (32 / 25%) are agent-chosen and unvalidated against any real provider quota. The first
  load test is where they get real numbers; they are per-configuration columns precisely so a
  workspace with an unusual quota is a settings change rather than a code change.

> **Mechanism superseded 2026-08-09 by ADR-0046. The intent stands and this ADR remains accepted.**
> ADR-0028 added the `worker` container during Stage 1 and nothing reconciled it with this decision.
> *"A per-configuration semaphore with a reserved share"* is a **process-local object**, and once batch
> dispatch runs in `worker` while interactive runs in `app`, the two priority classes no longer share
> it: each process initialises its own semaphore from the same column, so `max_concurrency: 32` becomes
> **64 in flight against one provider key**, and `reserved_interactive` reserves nothing from anyone
> — neither process contains both classes.
> ADR-0046 replaces the mechanism with two per-process caps, `interactive_concurrency` and
> `batch_concurrency`, and argues that the process boundary is a *stronger* guarantee than this
> semaphore ever gave: a semaphore could stop batch taking a slot, but never stopped it consuming
> event-loop time, TLS handshakes or connection-pool entries in the same process. What is genuinely
> lost is the floor-not-cap property named above — an idle gateway no longer donates its budget to a
> running suite. The defaults' successor numbers are A-134, still unvalidated for the same reason this
> ADR gave.

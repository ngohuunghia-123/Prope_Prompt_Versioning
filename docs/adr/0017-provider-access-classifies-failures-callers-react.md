# ADR-0017 — Provider Access classifies upstream failures; its callers decide what to do about them

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-095, A-097)
**Module**: provider-access, gateway, evaluation (written while locking provider-access)
**Related**: A-030, A-033, A-034, A-035, A-043, A-053, A-057, A-084, A-088, ADR-0013

## Context

The gateway's entire fallback branch turns on one question — was this an *upstream* failure or a
*caller* failure? A-034 states the rule and gateway.lock.yml calls the classification "the single
piece of logic that decides whether a fallback is even considered", filing it under the gateway's
unit tests.

Evaluation depends on the same distinction from the other side: A-057 makes a dispatch failure
`error` and never `fail`, and any error withholds the cost delta. Two modules, two consequences, one
underlying judgement.

The judgement itself requires provider knowledge. An OpenAI 429, an Anthropic `overloaded_error`, a
Gemini `RESOURCE_EXHAUSTED`, and a bare socket timeout are the same class expressed four ways. Only
provider-access has the adapter that knows this — so a classification made in the gateway would be a
provider matrix inside the latency-critical module, duplicated inside evaluation.

## Decision

**`dispatch()` returns a typed failure, and the type carries four separate facts.**

| Fact | Values |
|---|---|
| `class` | `credential_rejected`, `rate_limited`, `upstream_unavailable`, `timeout`, `model_not_available`, `content_filtered`, `invalid_request`, `provider_contract_violation` |
| `origin` | `provider` — the upstream said so; `prope` — Prope's own admission gate (ADR-0016) |
| `fallback_eligible` | whether serving the revision's fallback answer is a truthful response |
| `retryable` | whether a second attempt could plausibly succeed, with `retry_after_ms` when known |

Provider Access sets all four. It never decides what happens next.

- **The gateway** reads `fallback_eligible` and applies ADR-0013's pre-first-byte rule to it.
- **Evaluation** reads `retryable` and applies A-053 — transport errors only, at most two retries,
  its own loop, because A-088 keeps this module to exactly one attempt.

Two classifications are worth stating explicitly because they are the ones a reasonable person gets
wrong:

- **`content_filtered` is not fallback-eligible.** The provider did not fail; it refused, deliberately
  and deterministically, because of the content. Serving a canned answer in its place replaces a
  safety refusal with something that looks like a normal response, and it will do so every time.
- **`invalid_request` is not fallback-eligible.** A generation parameter the provider rejects is a
  defect in an *approved revision* (A-097), and the fallback exists for upstream failures, not for
  revisions that were never viable. Masking it would let a revision whose binding has never
  successfully run sit in production looking healthy.

`credential_rejected` and `model_not_available` are fallback-eligible but **not** retryable, and both
page. The fallback buys hours; the alert is what stops those hours becoming a quarter.

## Alternatives rejected

**The gateway classifies from the HTTP status.** Rejected: status codes are not portable across
providers, so this is a provider matrix in the module with the strictest latency budget — and a second
one inside evaluation. It also cannot see the transport-level cases at all, since by the time an error
reaches the gateway as a status there was no status.

**One `retryable` boolean instead of a class.** Rejected because it conflates three independent
things. A rate limit is retryable *and* fallback-eligible. A rejected credential is fallback-eligible
and *not* retryable. A content filter is neither. A timeout is both, but only for a caller with no
latency budget. One bit cannot express that, and the first time someone needs the distinction they
add a second bit next to it with no name for what it means.

**Let each caller classify from the raw provider error.** Rejected: it is the gateway-classifies
option with the duplication made explicit, and it puts the gateway's fallback rule and evaluation's
`error`-versus-`fail` rule on two independent readings of the same response. They will drift, and the
drift is invisible — both modules keep working, they just disagree about what happened.

**Have provider-access serve the fallback itself, since it knows the failure best.** Rejected on
ownership. The fallback answer is a field on the revision (A-032), reviewed and approved with it, and
this module has never heard of a revision — it receives a `provider_config_id` and a model string. It
would also mean a batch eval run could be handed a fallback, which A-034 forbids outright: an eval
that silently measures canned text is worse than an eval that errors.

**Make `fallback_eligible` a policy the caller configures.** Rejected as a knob that only ever gets
turned the wrong way. The interesting cases — content filtering, an invalid parameter — are exactly
the ones where a team under pressure would enable fallback to stop the alerts, and the result is a
system that answers policy refusals with approved-looking text.

## Consequences

- gateway.lock.yml's unit-test line for "the upstream-vs-caller failure classification table" moves
  here. The gateway keeps a much smaller test: given `fallback_eligible` and a first-byte state, does
  it do the right thing.
- Every call record carries the error class, so a misclassification is reconstructible after the fact
  rather than only reproducible. This matters because the mistake is invisible at the point it is
  made — the gateway does exactly what it was told.
- The table is unit-tested *as a table* (AC-5), enumerating every provider status and transport
  condition, rather than exercised incidentally through integration tests that happen to hit three of
  them.
- A new provider adapter must fill in this table, and that is the honest cost of adding one. It is the
  part of an adapter that cannot be inferred from the API documentation's happy path.

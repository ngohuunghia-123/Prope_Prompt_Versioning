# ADR-0015 — The OpenAI chat-completions shape is the internal dispatch contract

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-089, A-094, A-095)
**Module**: provider-access, gateway, evaluation (written while locking provider-access)
**Related**: A-026, A-030, A-043, A-053, ADR-0013, OQ-003, OQ-004

## Context

Two facts collide at this seam. The constraints table makes OpenAI wire compatibility
non-negotiable at the *edge* — "a near-miss breaks every client SDK". And OQ-004's answer makes the
*provider* the workspace's choice, which means the upstream response shape is not Prope's to assume.

Something has to translate, and the question is which module owns the translation and what shape the
dispatch seam carries. Two callers cross it — the gateway, which has the strictest latency budget in
the system, and the eval runner, which has none — and one success metric ("reported token counts
match the provider within ±2%") is a claim about parsing, not about arithmetic.

## Decision

**`dispatch()` returns the OpenAI chat-completions object.** Streaming returns OpenAI
chat-completion *chunk* objects. Provider adapters inside provider-access translate into that shape,
and the usage object is returned alongside it, always requested and never optional (A-089).

**Unknown fields pass through untouched.** When the upstream is itself OpenAI-compatible — the MVP's
only adapter (A-094) — a field Prope does not model reaches the caller unchanged.

The wire format the constraints table mandates for the edge is therefore also the internal contract.
There is exactly one translation in the system, it lives beside the credential and the model
catalogue, and it is the same code whether the call is production traffic or an eval case.

## Alternatives rejected

**The gateway translates.** Rejected on two counts. It puts a growing table of provider-specific
knowledge inside the module carrying the 50 ms budget, so every new provider becomes a change in the
hot path. And evaluation needs the same translation, so it grows a second copy — which destroys the
argument A-043 was made for: "one usage-parsing implementation, not two". Two parsers is how the
±2% metric becomes true on one path and untested on the other.

**A bespoke internal response shape, translated again at each edge.** Rejected as translate-out-and-
back for the common case: the provider is OpenAI-shaped, the caller wants OpenAI-shaped, and an
intermediate model buys nothing but a place to lose fields. Every field Prope forgets to model is
silently dropped in the middle, which is *precisely* the mechanism by which a near-miss reaches an
SDK. It converts a hard constraint into an ongoing modelling obligation nobody is watching.

**Return the provider's native response and let each caller deal with it.** Rejected: it is the
gateway-translates option with the duplication made explicit. Both callers grow a provider matrix,
they drift, and evaluation's `error`-versus-`fail` distinction (A-057) ends up resting on a different
reading of the same response than the gateway's fallback branch does.

**Normalise, but strip unknown fields for safety.** Rejected, and this is the tempting middle
ground — a closed schema is easier to validate and easier to test. The strip is the bug. Prope does
not know what a provider will add next, a consumer using a provider-specific field would find Prope
silently deleting it, and the failure is invisible: nothing errors, a field is just gone. Passing
unknown fields through means Prope's ignorance costs the consumer nothing.

**Normalise responses but not streaming chunks, since chunks are "just relayed".** Rejected because
it is only true for one adapter. A non-OpenAI-shaped provider's stream differs in framing, in
delta structure, and in where usage arrives; leaving chunks native would mean the gateway relays a
shape it cannot have anticipated the moment a second adapter ships — and streaming is already the
part of this build most likely to be wrong on the first try (module_map.md, gateway INVEST note).

## Consequences

- Adding a provider whose API is not OpenAI-shaped — Anthropic's Messages API, Google's Gemini API —
  is a real adapter with a real test suite, not a configuration entry. That cost is why A-094 keeps
  the MVP to one adapter kind and why OQ-016 asks which provider the pilot actually needs.
- The `adapter` column exists on `provider_config` from day one so the second adapter is additive.
- Contract tests parse `dispatch()`'s return value with a real OpenAI client SDK's own model rather
  than hand-checking keys — the same discipline the gateway's contract tests use, for the same
  reason: hand-built assertions are how a near-miss survives testing.
- The usage object's field names become part of this contract, since the ±2% metric depends on them,
  and they are asserted now. *Registered 2026-08-09 at step 5 as **INT-015** (the internal seam)
  and **INT-022** (the wire surface it mirrors); the generated schema comes from provider-access code
  at build time, so the assertion is the contract until it does.*
- ADR-0013's "the gateway sets `stream_options.include_usage`" is refined by this decision:
  provider-access composes the upstream request, so it is the module that asks for usage, and it does
  so unconditionally (A-089). The gateway keeps the caller-facing half — stripping the extra
  usage-only chunk from a stream whose caller did not ask for it.

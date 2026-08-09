# ADR-0013 — The fallback answer is a pre-first-byte decision

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-085, A-083, A-084)
**Module**: gateway, call-ledger (written while locking gateway)
**Related**: A-030, A-033, A-034, A-035, A-038, A-053

## Context

A-033 through A-035 settle *whether* a fallback answer is served: on an upstream failure, yes if one
is set; on a caller failure, never. They are silent about *when*, and streaming is where that silence
becomes a bug.

A streaming call commits to its outcome early. The moment the first chunk is flushed, the status line
is already `200`, the caller already holds partial content, and their SDK is already yielding tokens
into somebody's UI. An upstream failure after that point cannot be answered with "here is the fallback
instead" — there is no *instead* left.

The same seam raises a second problem that only appears in streaming. OpenAI-compatible providers omit
the usage object from a streamed response unless the request asks for it via
`stream_options.include_usage`. Whether Prope can report tokens and cost for a call would then depend
on a flag the *caller* sets — and two success metrics depend on those numbers, while the constraints
table forbids inferring cost from prompt length.

## Decision

**A fallback is reachable only before the first byte reaches the caller.**

- Upstream failure **pre-first-byte** — 5xx, timeout, rate limit, rejected credential, or an exhausted
  deadline: the fallback is served if one is set (A-033), otherwise the provider's error passes
  through translated into the OpenAI error shape (A-035). This covers every non-streaming call, since
  a non-streaming call has no first byte until it has all of them.
- Upstream failure **mid-stream**: the fallback is unreachable. The stream terminates with an
  OpenAI-shaped error chunk. No canned text is appended. The call record is written with
  `outcome = truncated` and the partial body (A-038), because the provider still charged for what it
  generated.
- `prope_gateway_upstream_error_total` is labelled `stage = pre_first_byte | mid_stream`, so the two
  are never one number.

**One deadline, no retry.** The gateway sets a single per-request deadline and does not retry
upstream. Exhausting it is an upstream failure and is fallback-eligible on the rule above.

**Usage is Prope's business, not the caller's.** The upstream request asks for usage regardless of
what the caller asked for, and the gateway strips the extra usage-only chunk from the caller's stream
if the caller did not request it. If usage still does not arrive, tokens and cost are recorded as
**unknown** and `prope_gateway_usage_missing_total` increments. They are never estimated.

> *Amended 2026-08-08 while locking provider-access.* This paragraph originally read "the gateway
> sets `stream_options.include_usage` on the upstream request". It does not: provider-access composes
> the upstream request (A-043), so the flag is set there and unconditionally (A-089, ADR-0015). The
> gateway keeps the caller-facing half — the strip — because that is a fact about the caller's wire
> contract. The decision is unchanged; only its address was wrong.

## Alternatives rejected

**Splice the fallback onto the truncated stream.** Rejected, and it is the tempting one — the caller
gets a complete-looking answer. What they get is a response that is half model output and half canned
text, joined at an arbitrary token boundary, that no human wrote and no reviewer approved. It is
outside everything the approval record describes, and the `x-prope-fallback` marker cannot even be set
honestly, because the response is not a fallback — it is a hybrid.

**Buffer the whole stream server-side so a fallback stays possible until the end.** Rejected: it
deletes streaming. The user's latency instruction is explicit ("redirect trước, lưu logs sau"), A-038
requires that accumulation never delay a chunk, and OpenAI wire compatibility exists precisely so that
a consumer's streaming UI behaves as it does today. Preserving a rare recovery path by destroying the
common path is the wrong direction.

**Retry the upstream before falling back.** Rejected: inside a latency-critical path a retry doubles
the worst case to buy an outcome the fallback already covers in milliseconds. It also multiplies load
against a provider that is, by hypothesis, already failing or rate-limiting. The eval runner retries
only on transport error (A-053) because it has no latency budget; the gateway has the strictest one in
the system.

**Let the caller's `stream_options` decide whether Prope gets usage.** Rejected: it makes an
accountability guarantee depend on a flag in someone else's code. "Reported token counts match the
provider within ±2%" and the cost figures behind every release decision would silently apply only to
the subset of consumers who happened to opt in, and nothing would report the gap.

**Pass the extra usage chunk through to callers who did not ask for it.** Rejected on wire
compatibility: an SDK that did not request `include_usage` does not expect a final chunk with an empty
`choices` array, and the constraints table says a near-miss breaks every client SDK. Prope's
bookkeeping is not the caller's problem.

**Estimate tokens by counting when usage is missing.** Rejected by a non-negotiable constraint: cost
must be measured from actual runs and never inferred from prompt token length (BR-07). An estimate
that looks like a measurement is worse than an honest gap — the gap is visible in
`prope_gateway_usage_missing_total` and pages; a plausible wrong number never does.

## Consequences

- The gateway carries an explicit notion of "first byte flushed" as a state, and it gates the fallback
  branch. This is the specific part of A-038's accumulate-after-close path most likely to be wrong on
  the first try, and it has its own chaos test (client disconnect and upstream failure injected on
  both sides of the boundary).
- Non-streaming calls are strictly simpler: they are always pre-first-byte, so they always have the
  full fallback behaviour. A consuming team that cannot tolerate a truncated answer has a real
  choice — turn off streaming for that call — and now it is a documented one.
- `outcome = truncated` becomes a first-class call-record value alongside `ok`, `fallback`,
  `caller_error`, and `upstream_error`, and it carries a real cost figure. call-ledger must price a
  truncated call rather than discarding it.
- `prope_gateway_usage_missing_total` must stay at zero. A provider that ignores `include_usage`
  fails A-030's "only providers returning a usage object are supported" and is a provider-access
  admission question, not a gateway workaround. *Discharged 2026-08-08 while locking provider-access:*
  the verification probe refuses such a provider before the configuration can be saved active (A-090),
  and `prope_provider_access_usage_missing_total` with its own alert catches one that starts ignoring
  the request later.

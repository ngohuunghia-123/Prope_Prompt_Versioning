# ADR-0065 — The SDK carries context to the gateway and never carries a prompt body back

**Status**: Accepted
**Date**: 2026-08-19
**Decision**: user ("we will build a fully supported SDK"), shape by agent under ADR-0063
**Module**: a new deliverable, `sdk/python` — not a ninth bounded context. It has no schema, no
routes, and no deployment target; it is a package a customer installs into their own process
**Supersedes**: nothing. **Amends**: nothing — the wire format it speaks is INT-022 exactly as it
stands
**Related**: A-012, A-021, A-079, A-114, A-161, ADR-0012, ADR-0021, ADR-0022, ADR-0026, ADR-0033,
ADR-0058, ADR-0063, ADR-0066, INT-022, OQ-152, OQ-153, OQ-154, BR-01

## Context

ADR-0063 makes the SDK the integration path. That leaves one question that decides whether Prope
survives contact with its own convenience layer:

> When an application needs a prompt, does the prompt text travel to the application, or does the
> application's request travel to the prompt?

Both comparables answer *the text travels*. PromptLayer's `client.run(prompt_name=...)` fetches the
template and their own docs note it "adds latency from fetching templates"; Langfuse's
`get_prompt("movie-critic", label="production")` returns the template for the application to compile and
send onward itself. It is the obvious shape. It is also the shape that would quietly cost Prope its
product.

**Three things break if the body travels.**

*The charter clause breaks literally.* Prope's stated promise is that a consuming product "calls a
prompt by model name and **never holds a copy of the text**". An SDK that fetches templates puts the
text in the customer's process memory, their logs, their error reports and their heap dumps. The
promise becomes a description of one code path rather than a property.

*What ran becomes unverifiable.* Once the application holds the template, it renders it, and Prope
records what it *sent* rather than what was *used*. A caller that concatenates one extra sentence after
fetching is indistinguishable, from Prope's side, from one that did not — so `version_id` on a call
record stops meaning "this revision produced this call" and starts meaning "this revision was fetched
at some point beforehand". That is the traceability half of the core value, gone silently.

*Release control becomes advisory.* A fetched template can be cached, pinned, or fetched once at boot
and held for a month. Withdrawing a release stops affecting anything already running, which is exactly
the property ADR-0022 and A-114 refuse to cache the *permission* check for: revocation has to take
effect on the very next request, and it cannot if the next request never asks.

## Decision

**The SDK sends calls to the gateway and never fetches a prompt body. There is no `get_prompt`.**

### 1. The one hard rule

No method on the SDK returns prompt text, a template, or a revision body — not for rendering, not for
inspection, not for a debug flag. The gateway composes the system message from the released revision and
dispatches it; the SDK's request contains only the caller's own messages and variables, exactly as
INT-022 already defines.

This is stated as a rule rather than an outcome because it is the thing that will be re-proposed. The
request *"just let me see the prompt for debugging"* is reasonable, arrives constantly, and is answered
by the web application — where the reader is a person with `prompt.read`, not a process with a consumer
key. A consumer key must not be able to read a prompt body, and adding a method that does so would make
every leaked key a prompt exfiltration tool. It would also make BR-01's private-by-default meaningless
at the one boundary where it is cheapest to breach.

### 2. What the SDK is for, then

If it does not carry bodies, it carries **context** — and that is not a consolation prize, it is the
half a gateway cannot reach on its own.

**Chain threading, automatically.** ADR-0058 makes a conversation a caller-supplied correlation:
`prope.conversation_id` on every call, `prope.parent_call_id` naming the step before. Correct by hand
and tedious by hand — the playground's agent mode threads six calls and every one of them is a place to
get it wrong. In the SDK it is a context manager that remembers the previous `call_id` and fills both
fields. A chain assembled by the SDK is correct by construction, which is what makes the conversation
graph worth reading.

**The local steps a gateway is blind to.** The tool call that raised, the retrieval that returned
nothing, the guard that fired — none of these are LLM calls, so no proxy sees them, at any level of
effort. They are the difference between *"the model hallucinated"* and *"the retrieval returned nothing
and the model filled the gap"*, which is the distinction the improvement-agent module exists to make.

**The SDK's surface reserves them; their storage is not decided here.** A non-call node in a
conversation graph is a real extension to `ledger.call_record` — a sink with a forbidden outbound edge
and a check constraint per row shape — and designing it inside an SDK ADR would be deciding a schema in
the wrong document. It is **OQ-154**, it blocks the improvement-agent module and nothing else, and the
v1 SDK ships without it rather than shipping a method that silently drops data.

### 3. Thin, and with no dependency on the `openai` package

The SDK speaks INT-022 over HTTP directly. It does **not** wrap, subclass or monkey-patch the `openai`
client.

Wrapping is the obvious ergonomic shortcut and it imports somebody else's release cadence into Prope's
support surface: every `openai` major version becomes a compatibility matrix entry, and a customer
pinned to an old one becomes a bug Prope cannot reproduce. A-012's *debuggable by one person* clause
covers this — the SDK is one HTTP client, one request shape, one response shape, and a stack trace from
a customer's process has to be readable without knowing which version of a third-party library they
have.

It also keeps the migration honest. The skill (ADR-0066) rewrites `openai.chat.completions.create(...)`
into `prope.chat(...)`; if the SDK were a drop-in wrapper the rewrite would be a one-line import swap
that *looks* migrated while every prompt body stays exactly where it was.

### 4. It fails toward the caller, never toward silence

The SDK adds no retry that changes semantics, no local cache of anything, and no fallback that answers
from somewhere other than the gateway. A gateway error is raised, typed, carrying the machine `code`
from the envelope (ADR-0053) so the caller can branch on it.

The reason is the same as everywhere else in Prope: a convenience layer that quietly answers when the
governed path is unavailable is a way for an ungoverned answer to reach production, and that is the one
outcome the whole system exists to prevent.

## Alternatives rejected

**`get_prompt()` / `run(prompt_name=...)` — fetch the template, render locally.** What both comparables
ship, and what most people expect. Rejected on all three grounds above; the decisive one is that it
makes `version_id` on a call record a claim rather than a fact.

**Fetch the template but require the SDK to send back a hash of what it rendered.** A serious attempt at
keeping verifiability while gaining the offline path — and it fails on its own terms: the hash is
computed by the same process that may have modified the text, so it attests to nothing an adversarial or
merely buggy caller could not forge. Verification that the verified party performs is not verification.

**Wrap the `openai` client so migration is an import swap.** Rejected in §3. The strongest argument
*for* it is the strongest argument against: a migration that costs one line is a migration that moved
nothing.

**Ship an OpenTelemetry-native SDK instead, emitting `gen_ai.*` spans.** The market-standard shape, and
genuinely attractive for the local-steps problem — the semantic conventions already model tool calls.
Rejected as the *primary* surface because OTel is a telemetry protocol and Prope's SDK has to carry a
request that must be *answered*, not merely observed. Emitting OTel spans **alongside** the gateway call
is not rejected and is the likely answer to OQ-154; it is deferred rather than decided.

**No SDK; document the wire format and let customers call it.** The status quo, and the reason ADR-0063
was needed. `curl` is a specification, not an integration.

## Consequences

- **Prope acquires its first distributable with a version it does not control.** Deployment was 7
  services and 2 images (ADR-0033), all Prope's own. An SDK runs in a customer's process at a version
  Prope cannot force. **OQ-152** carries the policy: which languages, which supported versions, and what
  an old SDK meeting a new gateway is required to do (the answer must not be "fail").
- **The gateway's wire format becomes a public contract with two consumers**, the SDK and every
  OpenAI-compatible client. INT-022 was already public; what changes is that breaking it now breaks
  installed software rather than a configuration line.
- **`prope.chat()` cannot be tested against a mock that returns a body**, because there is no body to
  return. SDK tests run against the real gateway app with a stubbed provider, exactly as
  `tests/integration/test_gateway_resolve_released.py` already does.
- **The improvement-agent module gains a path and loses its blocker.** It was unreachable from a proxy —
  tool errors and retrieval failures happen where a proxy cannot see. It is now reachable, and gated on
  OQ-154 rather than on architecture.
- **OQ-153 closes.** Whether `model` should name the provider's model with `"auto"` meaning *use the
  revision's* was a knot created by having only the OpenAI wire format to carry Prope-specific intent.
  An SDK carries intent in named arguments; there is nothing left to overload.
- **The support surface now includes somebody else's stack trace.** This is the real ongoing cost, and
  §3's thinness is the mitigation rather than a style preference.

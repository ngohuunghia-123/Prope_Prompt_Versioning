# ADR-0011 — The caller supplies the conversation; the system prompt is the released revision's

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-077, A-078)
**Module**: gateway, prompt-registry, evaluation (written while locking gateway)
**Related**: A-011, A-022, A-024, A-046, ADR-0001

## Context

The gateway must be wire-compatible with the OpenAI chat-completions request, which carries
`messages: [...]` — an array that ordinarily includes the system message. The revision carries a
prompt body which is "one plain-text system message with optional `{{variable}}` placeholders"
(A-011). Both want the same slot, and nothing written so far says how they combine.

Two questions fall out and neither has a default in the OpenAI shape, because OpenAI has no concept
of a server-side prompt:

1. What happens when the caller sends a message with role `system`?
2. Where do values for `{{variable}}` placeholders come from? The request has no field for them.

This is not a formatting detail. Prope's claim to the Developer persona is that the text running in
production is the revision that was diffed, evaluated, and approved. Whatever answers question 1
decides whether that claim is true.

## Decision

**The revision's body is the system message. It is always first, and it is the only one.**

- The caller's `messages` array supplies the conversation: `user`, `assistant`, and `tool` roles.
- A message with role `system` is **refused** with an OpenAI-shaped `400`, naming the model name and
  stating that it carries its own system prompt. No upstream dispatch occurs.
- `{{variable}}` placeholders are filled from an optional top-level `prope` object on the request:
  `{"prope": {"variables": {"customer_name": "..."}}}`. Client SDKs reach this through their
  `extra_body` affordance, and it is symmetric with the `prope` object A-033 already puts on the
  response.
- A placeholder with no value is a caller error — an OpenAI-shaped `400` naming the missing variable.
  A request containing a literal `{{customer_name}}` is **never** dispatched upstream.
- Variables the template does not use are ignored. The missing-variable check already catches the
  typo that would otherwise hide behind an unused key.
- Generation parameters, provider, and model stay the revision's; the caller cannot override them
  (A-024). Parameters the caller sends that Prope owns are refused on the same terms as a system
  message.

Variable **values** are caller data and are treated exactly like a request body: never in a log line,
never in a metric label (A-046). Their names may be logged.

## Alternatives rejected

**Append the caller's system message after the revision's.** The obvious accommodation, and the one
that quietly destroys the product. The text actually in production would then be a concatenation
nobody reviewed: the diff, the eval run, and the approval all describe the revision's half only, and
the half that arrives at runtime is whatever a consumer's code happens to contain. Every eval result
becomes a measurement of something other than what runs. The failure is invisible — everything works,
the numbers look right, and they are describing a different prompt.

**Silently drop the caller's system message.** Worse than appending, and worse than refusing. The
consumer's code says their instructions apply; the model never sees them; nothing anywhere reports
the discrepancy. They debug the model's behaviour for a week.

**Let the caller's system message replace the revision's when present.** This is not a gateway with
governance; it is a proxy. The released pointer, the approval record, and the eval suite would all
describe text the caller chose to ignore.

**Put variables in a header** (`x-prope-var-customer-name`). Rejected: header values are ASCII-ish
and size-limited, prompt variables are neither, and structured data would need an encoding nobody
would enjoy debugging. It also splits caller data across two places for logging and redaction, and
A-046's rule is easier to hold when body-shaped data lives in the body.

**Fill placeholders from the last user message by convention** — parse it, or expect JSON. Rejected:
it makes the wire format guess at intent, and a prompt whose conversation legitimately contains braces
would break in a way no error message could explain.

**Allow the literal `{{name}}` through when unfilled.** Rejected outright. The model receives text
that looks like a template and answers plausibly anyway; the consumer ships a response referring to
`{{customer_name}}`, or worse, a hallucinated substitute. An unfilled placeholder is the caller's bug
and it should surface as the caller's error, before any money is spent upstream.

## Consequences

- Integrating with Prope requires deleting the system message from existing client code. This is the
  most likely first-integration failure, so it fails on the first call with a message that says what
  to delete, and it is counted (`prope_gateway_rejected_system_message_total`).
- The eval runner and the gateway compose calls identically — the same revision body, the same
  substitution — which is what makes an eval result a statement about production behaviour rather
  than about a laboratory (A-027, A-043).
- Variables become part of the reviewed contract: a revision that introduces `{{tier}}` breaks every
  caller that does not send it, and that break is visible in the diff at review time. Whether the eval
  suite should assert a revision's variable set is evaluation's question, not the gateway's — noted
  for the step-6 sweep.
- The `prope` request object is a documented extension point. Anything added there later is additive
  and ignorable by older clients, which is the property that made it preferable to a header.

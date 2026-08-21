# ADR-0059 — The gateway observes a call it cannot resolve, and only that one

**Status**: Accepted
**Date**: 2026-08-18
**Decision**: user (raised as "the integration is very hard and nobody will rebuild their codebase to use this")
**Module**: gateway — a second serving mode, entered on one of five resolve-miss reasons and not the other four
**Related**: A-020, A-022, A-024, A-026, A-033, A-035, A-078, A-081, A-084, A-097, A-116, A-143,
ADR-0011, ADR-0012, ADR-0015, ADR-0017, ADR-0050, ADR-0060, BR-01, BR-03, OQ-006, OQ-013, OQ-147,
INT-022, INT-034

## Context

Prope asks a team to do three things before it returns anything: take the prompt out of the code,
write down its variable contract, and change the call site to name a prompt instead of a model. Only
after all three does the product pay — approval before release, restore without redeploy, a call
traceable to the revision that served it.

**The wiring was never the hard part.** INT-022 is OpenAI-shaped, so for any client that accepts a
`base_url` the change is one line, and every framework worth naming accepts one. What a team actually
refuses is the middle step: a prompt in code is an f-string, assembled across call sites, and nobody
has ever written down which spans are variable. That is archaeology, and under the current design it
is billed in full **before the first screen has anything on it**.

There is a discovery problem underneath the adoption problem, and it is the one `positioning.md` §1
leads with: prompts are scattered across code, Sheets, Notion and chat, and nobody knows what is
running. T1 in `positioning.md` §12 already narrowed auto-discovery to *"positioning and Release 2+"*,
with the MVP demonstrating deliberate import of one repo and one Sheet. **That narrowing is about
scanning repositories.** It says nothing about the one place a production prompt is guaranteed to
appear in full — already assembled, already interpolated, and already in front of a system the team is
being asked to point a client at: **the request**.

## Decision

**The gateway gains a second serving mode. When an authenticated key is enabled for it, a request
whose model name is unknown to the registry is forwarded upstream unchanged and recorded as an
observation, rather than refused.**

The mode is entered on **exactly one** of `MissReason`'s five values.

| resolve outcome | observe-enabled key | observe-disabled key |
|---|---|---|
| resolved | serve the released revision | serve the released revision |
| `UNKNOWN_MODEL` | **passthrough and observe** | 404, unchanged |
| `NOT_PERMITTED` | 404, unchanged | 404, unchanged |
| `NO_RELEASE` | 404, unchanged | 404, unchanged |
| `PIN_NOT_FOUND` / `PIN_NOT_APPROVED` | 404, unchanged | 404, unchanged |

**The three rows that do not move are the decision.** They read as conservatism and they are not:

- **`NOT_PERMITTED` must never become passthrough.** A-116 makes a scope refusal byte-identical to an
  unknown model name so that a leaked key cannot enumerate the registry. If the two diverged for an
  observe-enabled key, that divergence *is* the enumeration oracle — and a worse one than the original,
  because the distinguishing response is one the workspace paid a provider for.
- **`NO_RELEASE` must never become passthrough.** That name belongs to a prompt somebody registered.
  Forwarding it would let a caller go on serving their own inline copy of a prompt Prope is supposed to
  govern, and Prope would file the traffic as *unmanaged*: a governed prompt silently un-governing
  itself, which is the worst single outcome available to this product.
- **A pin naming an unapproved revision must never become passthrough**, for the same reason one step
  further in — BR-03 exists to refuse precisely that request.

The mode is therefore reachable only where Prope has, and has ever had, nothing to say.

### What the mode does not do

- **It does not compose.** `compose()` and `render()` are not called. ADR-0011's rule — the revision's
  body is the system message and the only one — governs *serving a revision*, and this path serves
  none. The caller's message array, system message included, goes upstream verbatim.
- **`system_message_not_allowed` is unchanged and still fires** whenever the model name resolved. The
  gateway lock calls it *"the single most likely first-integration mistake"*; it stays a 400 on every
  path where a revision was found, and it is unreachable on the path where none was.
- **`prope.variables` is not read**, because there is no `{{placeholder}}` to fill. Sending one is not
  an error; it is recorded and ignored. A-078 governs a revision body, and there is no revision body.
- **Generation parameters pass through as the caller sent them.** A-024 forbids a caller overriding
  *the revision's* parameters so that the approval record describes what ran. Here there is no revision
  and no approval, so there is nothing to protect, and A-097's rule applies one layer out unchanged:
  the provider's answer to a bad parameter is the caller's answer.
- **`model` is sent upstream verbatim as `upstream_model`.** The gateway does not map it, alias it, or
  validate it against the model catalogue. An unknown provider model is the provider's 404, relayed.
- **No fallback answer is served.** A fallback belongs to a revision (A-033, A-035). An upstream
  failure on this path is an upstream failure, translated by ADR-0017 as it always is.
- **The response carries no `prope` identity block and no `x-prope-version-id`**, because nothing of
  ours served it. It carries `x-prope-call-id` and one new header, `x-prope-observed: true`, so a
  developer reading a response can tell at a glance that Prope forwarded rather than served. The body's
  `id` is still rewritten to `chatcmpl-cal_...`: it is the caller's only handle on the row, and the
  `ServedIdentity` docstring's argument for overwriting the provider's id does not weaken here.

### The switch is one nullable column, and it is default-off

`access.api_key` gains `observe_provider_config_id text NULL`. NULL — the default, and the value every
existing row already has — means **this key behaves exactly as it does today**, which is the property
that makes the change safe to ship. Non-NULL both enables the mode and answers the question the mode
cannot otherwise answer: *whose credential pays for a call naming a prompt we do not have?*

The bearer slot is already occupied by the Prope key, so the caller cannot hand us a provider
credential even if we wanted one — and A-025 says we would not. The workspace therefore registers a
provider configuration first, which it must do to use Prope at all, and points the key at it. That is
the honest price of "change one line": one line in the client, and one dropdown in Prope.

Putting the switch on the key rather than on the workspace is deliberate. Observation is how a team
tries Prope against production traffic; the blast radius of getting it wrong should be one integration,
revocable in one row, and visible on the same screen that already lists what a key may resolve.

## Alternatives rejected

**Recognise the fingerprint and substitute the released body.** The tempting rung: the client keeps its
inline prompt, Prope spots the fingerprint, and serves the approved revision instead — restore without
redeploy, with no code change at all. It demonstrates beautifully. **Rejected**, and not narrowly. The
match is a heuristic over text; a false positive silently replaces a production system prompt with a
different one, and the failure is invisible from the client, whose code still contains the old text.
`positioning.md` §3.1 is explicit that the developer is persona #2 and holds a veto, and that the veto
is pulled *the first time the register causes a production incident*. This is the feature most likely
to pull it. The supported route to the same value is: adopt the observation, then change the model
name — one line, once, deliberately, by somebody who chose to.

**Forward every miss, including scope refusals.** One branch instead of five. Rejected in the table
above: it converts A-116's indistinguishability into an enumeration oracle, and it lets a registered
prompt de-register itself by traffic.

**Accept the provider key as the bearer and forward it upstream.** Would make the mode
zero-configuration. Rejected — the gateway must authenticate the workspace before it knows anything at
all, and the credential rule (`00_context.md` constraints, A-025) is that provider credentials are
workspace-supplied, encrypted at rest, and decrypted only by provider-access. A pass-through secret is
a second credential path with no encryption, no rotation, and no redaction story.

**A separate endpoint — `/v1/observe/chat/completions`.** Cleanest separation, no branch in the hot
path at all. Rejected because it defeats the purpose: the entire value is that the client changes one
line and nothing else, and every OpenAI SDK appends `/chat/completions` to the base URL itself.

**Scan repositories instead.** What `positioning.md` T1 already deferred, and this decision does not
revive it. The difference is worth naming anyway: a scan finds the string; the request finds the string
*and* proves it is live *and* prices it. A scanner cannot tell a dead prompt from a hot one.

## Consequences

- **The gateway declares a second serving mode in its lock.** `in_scope` grows one line; `non_goals`
  grows two — the substitution rejected above, and any refusal reason other than `UNKNOWN_MODEL`
  entering the mode.
- **Three acceptance criteria are owed**, and all three assert a *refusal* rather than a success, which
  is where this decision's risk actually lives: that an observe-enabled key still receives a
  byte-identical 404 for `NOT_PERMITTED` and for `NO_RELEASE`; that an observe-disabled key is
  unaffected on every path; and that a resolved model name carrying a caller system message is still a
  400 for both kinds of key.
- **`resolve_miss_total`'s existing `reason` label becomes load-bearing** rather than diagnostic. It is
  already emitted per `MissReason`, and it is now the metric that shows whether the entry rule holds. A
  new counter, `observed_call_total`, is labelled by outcome only — never by model name, which is
  caller-supplied text and would be unbounded (ADR-0030).
- **The p95 budget is untouched on the served path.** The branch is taken after resolution has already
  missed, on a request that was going to be a 404.
- **A-020 is not satisfied by this ADR and is not waived by it.** Observation ingests real production
  prompt bodies at volume, from a client that made no decision to submit them. That is policy, it is
  raised as OQ-147, and the column above is default-NULL precisely so this can ship while the answer is
  outstanding.
- **Where the body goes, and why it is not a call body, is ADR-0060.** This ADR decides only when the
  gateway forwards.

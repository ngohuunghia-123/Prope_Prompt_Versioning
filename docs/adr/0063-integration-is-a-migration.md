# ADR-0063 — Integration is a migration, and Prope stops pretending otherwise

**Status**: Accepted
**Date**: 2026-08-19
**Decision**: user ("instead of building the app easy-to-integrate but never found a right solution
[…] we will build a fully supported SDK (dont try to solve) and write a Agent Skill for them to
self integrate (scan and upload all prompt to prope, track relationship), or our team will integrate
for customer")
**Module**: global — the integration story. gateway (unchanged, and now the only serving path) /
prompt-observation (demoted, ADR-0064) / a new SDK deliverable (ADR-0065) / a new migration skill
(ADR-0066)
**Supersedes**: nothing structural. **Amends**: ADR-0059's *purpose*, not its mechanism —
see ADR-0064
**Related**: A-012, A-020, A-116, A-152, A-161, A-162, ADR-0021, ADR-0022, ADR-0059, ADR-0060,
ADR-0061, ADR-0062, ADR-0064, ADR-0065, ADR-0066, OQ-006, OQ-013, OQ-151, OQ-152, OQ-153, BR-01

## Context

ADR-0059 was written to answer one sentence: *most prompts are managed in-code and have never been
exposed; after Prope is built, integration is very hard, and a team will not rebuild their codebase
just to use it.* The answer was to make Prope adoptable **without** a code change — point an
OpenAI-compatible client at the gateway, and calls Prope cannot resolve are forwarded to the provider
and filed as observations.

**It shipped, it works, and it is now proven end to end.**
`tests/integration/test_gateway_observes_a_legacy_app.py` drives the exact traffic an unmodified
product sends — a provider model name, a `system` message, no `prope` block — and asserts the call is
answered normally, filed in the key's folder, grouped by fingerprint across an interpolated date, and
kept separate from a different persona. Six tests, all passing. Nothing below is a claim that the
mechanism is broken.

**The mechanism works and the strategy does not**, and it took four consecutive failures to see why.

### An observation delivers none of the four non-negotiables

This is the whole finding, and it should have been checked before ADR-0059 rather than after.

| non-negotiable | what an observation gives |
|---|---|
| Human approval before production | none — the prompt is already in production, unapproved, and Prope watched it go |
| Only `Approved` revisions may be released or resolved | none — there is no revision |
| Edit, review/approve and release are separate permissions | none — there is nothing to edit; the body lives in the customer's repository |
| Prompts are private by default | the only one that holds, and ADR-0061 had to be written to give it something to hold onto |

An observed prompt is **read-only by construction**. It is a photograph of a string that is still
compiled into somebody else's binary. Nobody can edit it in Prope, nobody approved it, and changing it
still means a deploy. The core value — *no prompt reaches production without a recorded human
approval, and every call can be traced back to the exact revision that served it* — is untouched by
every observation Prope will ever file.

So ADR-0059 optimised the **on-ramp** while the **destination** stayed unreachable. That is the error,
and it is a strategic error rather than a technical one: an easier road to a place that cannot do
anything is not an improvement.

### And the on-ramp was not even the cheap one

Worse, the ask ADR-0059 makes is the *most* expensive in the market, not the least. Three asks exist,
in increasing order of how hard a "yes" is:

1. **send us telemetry** — asynchronous, out of band, nothing in the request path;
2. **route your production traffic through us** — now in the critical path;
3. **route your traffic through us *and* hand over your provider credentials.**

Prope's observe path is **(3)**. `api_key.observe_provider_config_id` names a stored, KEK-encrypted
credential and `dispatch` decrypts it, because forwarding has to authenticate to the provider as
somebody. There is no passthrough mode. A team adopting the observe path uploads their provider key
**and** puts an unevaluated system in front of production traffic. That is a security review, not an
integration — which is why the pilot's own first attempt failed three times on configuration before
producing a single row.

The market says the same thing from three directions:

- **PromptLayer does not proxy at all.** Its zero-refactor on-ramp is `instrument_openai()` — one call
  before the first request, OpenTelemetry-based, asynchronous, no traffic routing; in JavaScript it is
  a launch flag (`node --import promptlayer/register`) and touches no source. It captures system
  prompts and message content by default, gated by the standard
  `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`.
- **Langfuse built a proxy and publicly recommends against it**: *"in most production grade
  applications, the benefits do not outweigh the risks of using an LLM Proxy and thereby introducing a
  single point of failure"* — naming latency, reliability, security/privacy, and the loss of
  client-side metrics.
- **Helicone, the most proxy-first comparable, offers passthrough** — the caller sends their own
  provider key and Helicone stores nothing. Prope has no such mode and cannot easily have one, because
  a passthrough key cannot be used to serve a *released revision* on the same connection.

### And nobody has solved the part Prope is actually good at

The other half of the research is the reason this decision is a pivot rather than a retreat.
PromptLayer's `tracking-templates` runs the **wrong way**: it associates a logged request with a
template somebody already created by hand. There is no *"here are the prompts we saw — adopt this
one"*. Their quickstart begins with *create a prompt in the dashboard*; it assumes a greenfield, not a
migration.

Prope has the opposite inventory. Fingerprint grouping, timestamp masking, positional variable
inference, and an adoption flow that ends in a real revision with a real approval — all built, all
tested, and all sitting behind the most expensive door in the market.

**The conclusion is not "make the door cheaper".** A cheaper door to a read-only room is still a
read-only room. The conclusion is that the customer has to walk through, and Prope's job is to carry
their luggage.

## Decision

**Integration is a migration. Prope will help perform it rather than avoid it.**

Three deliverables, each with its own ADR, and one demotion.

### 1. A first-class SDK is the integration path — ADR-0065

Not a compatibility shim and not an apology for the gateway. The SDK is where chain context, tool
outcomes and retrieval steps enter Prope, and those are things a gateway **structurally cannot see**:
the gateway observes prompts in and completions out, while the tool call that failed and the retrieval
that returned nothing happened inside the application. The improvement-agent module was never reachable
from a proxy, at any level of effort.

The SDK's hard constraint is in ADR-0065 and it is the one that keeps this from becoming Langfuse: **it
sends calls to the gateway and never fetches a prompt body back.**

### 2. Migration is proposed by an agent and performed by a person — ADR-0066

A skill the customer runs inside their own repository, with their own coding agent, which reads the
source and proposes: here are the prompts, here are their variables, here is the call graph, here is
the diff that would replace each literal with a gateway call.

An agent reading source beats a proxy watching traffic on every axis of discovery:

| | observation (ADR-0059) | agent reading the repository |
|---|---|---|
| prompt behind a rarely-taken branch | invisible until it runs | found |
| variable names | inferred by diffing renders — `{{var_1}}`, `{{var_2}}` (A-154) | the real identifiers from the source |
| chain structure | not visible at all | the call graph is in the file |
| **rewriting the call site** | impossible | **a diff a person reviews** |

The last row is the pivot in one line. The refactor was never the thing to avoid; it was the thing to
automate. Every target customer already runs a coding agent in that repository.

### 3. White-glove integration is a learning instrument, not a service line

Prope's own team integrating for early customers is correct and expected — and it is bounded by one
rule: **every manual integration ends with a rule added to the skill.** A migration performed by hand
that teaches the skill nothing has been performed twice.

### 4. Observation is demoted to a migration audit — ADR-0064

Not deleted. ADR-0059, ADR-0060, ADR-0061 and ADR-0062 keep every table, constraint, policy and test
they shipped. What changes is what the machinery is *for*: after a migration, an observing key pointed
at the application answers the one question the migration itself cannot — **what did we miss?** A
prompt still forwarding is a prompt the scan did not find. That is a completeness proof no other
mechanism in Prope can produce, and it is worth more than the adoption story it replaces.

## Alternatives rejected

**Make the on-ramp cheaper: accept OTLP and become an OpenTelemetry backend.** The strongest
alternative, and the one the market has converged on — Langfuse at `/api/public/otel`, Braintrust at
`/otel/v1/traces`, Phoenix natively; the GenAI semantic conventions already standardise
`gen_ai.system_instructions`, `gen_ai.input.messages` and `gen_ai.output.messages`, so an app running
OpenLLMetry or PromptLayer's own instrumentation would need **one environment variable** to fill Prope's
observation inbox. Cheaper than the `base_url` swap, with no credentials, no latency and no single
point of failure.

Rejected as the **primary** path for the reason this whole ADR exists: it is a cheaper road to the same
read-only room. It would produce a larger inventory of prompts nobody can edit, approve, or release,
and it would put Prope into direct competition with three mature observability products on the axis
where Prope is weakest and they are strongest. It is recorded as **OQ-151** rather than dismissed,
because as an *audit* intake — ADR-0064's job — it is strictly better than a forwarding proxy, and the
question of whether the audit should ingest OTLP instead of forwarding is a real one that does not need
answering today.

**Keep observation as the adoption story and fix the ergonomics.** The path this session was on for
four attempts: better error messages, a create-time observation switch, a diagnostic command. All of
those were built or specified and none of them change the fact that the destination is read-only. This
was the failure mode worth naming: **the ergonomics were being fixed because they were fixable, not
because fixing them helped.**

**Passthrough credentials, so the observe path stops asking for a provider key.** Would genuinely
reduce ADR-0059's ask from (3) to (2). Rejected because it cannot coexist with serving: a passthrough
key authenticates the caller to *their* provider, and a released revision resolved on the same
connection has to be dispatched with the *workspace's* configuration. Two credential models on one
endpoint is a branch on the hot path that decides which secret to use, which is the last place that
decision should live.

**An SDK that fetches prompt bodies, like PromptLayer's `run` and Langfuse's `get_prompt`.** The
obvious shape, shipped by both comparables. Rejected in ADR-0065 with its own reasoning: it puts the
prompt text back in the application, which breaks the charter clause *"never holds a copy of the
text"*, and it makes what actually ran unverifiable.

**Do nothing and let customers integrate manually.** The status quo before ADR-0059, and it is what
the survey says produces zero adoptions. The skill exists precisely because *"just rewrite your call
sites"* is a true instruction nobody follows.

## Consequences

- **ADR-0059's problem statement is retired; its mechanism is not.** No migration, no dropped table, no
  removed test. `tests/integration/test_gateway_observes_a_legacy_app.py` keeps passing and changes
  meaning: it is now the audit path's test. ADR-0064 carries the demotion.
- **The gateway is the only serving path and therefore the only enforcement point.** This was already
  true and is now load-bearing: every alternative that would let an application render a prompt locally
  is rejected by name, in ADR-0065, rather than left as an option somebody re-proposes.
- **`playgrounds/chatbot-app/index.html` changes what it demonstrates.** It was rewritten this session
  into an unmodified third-party chatbot to exercise the observe path. It keeps that job under the new
  reading — it is the *before* picture and the audit's test subject — and `integrated.html` becomes the
  *after* the migration produces. Neither is deleted.
- **A-020 binds the skill harder than it binds anything else so far.** A codebase scanner that uploads
  prompt text is, precisely, real corporate prompts entering Prope — the thing A-020 forbids until
  OQ-006 and OQ-013 are answered. ADR-0066 makes dry-run the default and requires a reviewed manifest
  before any upload; that is not caution, it is A-020 expressed as a default.
- **The `model` override question dissolves.** OQ-148's neighbour — whether `model` should name the
  provider's model with `"auto"` meaning *use the revision's* — was a knot created by having only the
  OpenAI wire format to carry Prope-specific intent. An SDK carries intent in its own arguments, so
  there is nothing to overload. Recorded as closed-by-decision in **OQ-153**.
- **Prope acquires a second distributable.** Until now the deployment shape was 7 services and 2 images
  (ADR-0033), all of it Prope's own. An SDK is a package a customer installs into *their* process, with
  a version skew Prope does not control. **OQ-152** carries what that costs: language coverage,
  supported-version policy, and what happens when an old SDK meets a new gateway.
- **A-012's *debuggable by one person* clause now covers somebody else's stack trace.** An SDK failing
  inside a customer's application is a support surface Prope has never had. It is a reason to keep the
  SDK thin — ADR-0065's no-fetching rule is also what keeps it small enough to reason about.

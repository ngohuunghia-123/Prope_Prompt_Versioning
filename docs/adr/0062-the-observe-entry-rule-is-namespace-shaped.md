# ADR-0062 — The observe entry rule is namespace-shaped, because the name-shaped one was unreachable

**Status**: Accepted
**Date**: 2026-08-18
**Decision**: user (the per-folder proposal, which is what exposed this)
**Module**: gateway (the entry rule) / access-control (the scope check that pre-empted it) /
prompt-observation (where the body lands)
**Amends**: **ADR-0059's entry rule**. **Supersedes**: A-153, replaced by A-156
**Related**: A-021, A-081, A-116, A-143, A-152, A-153, A-156, A-159, ADR-0059, ADR-0060, ADR-0061,
BR-01, OQ-147, INT-004, INT-022

## Context

**ADR-0059's forwarding mode, as written yesterday, cannot fire.** This ADR records that, and fixes it.

A-153 says a request is forwarded when resolution misses with `MissReason.UNKNOWN_MODEL` on an
observe-enabled key. Following the code rather than the ADR, neither of the two shapes a real
unmanaged model name arrives in ever reaches that value.

**`gpt-4o`, `gpt-4o-mini`, `claude-sonnet-4` — no slash.** `parse_model_reference` calls
`ModelName.parse`, which requires A-021's `namespace/name` and raises `ModelNameInvalid` on a bare
name. `chat_completions` translates that to `model_not_found` **before `resolve_binding` is called at
all**. No `MissReason` is ever computed. These are the model names of every OpenAI-shaped client on
earth, and they were unreachable by construction.

**`openai/gpt-4o`, `meta-llama/Llama-3-70b` — a slash, so it parses.** It reaches `resolve_binding`,
where the very first statement is:

```python
if not await may_resolve(db, key.key_id, reference.model_name):
    raise _missed(MissReason.NOT_PERMITTED, started, reference.raw)
```

A key's scope is a list of *prompt names* (A-081). `openai/gpt-4o` is not a prompt name, so it is not
in any key's scope, so every such request is `NOT_PERMITTED` — which A-153 forbids forwarding. Correctly
forbids: that rule is the security decision in ADR-0059 and it is not the thing that is wrong.

So the mode is dead in both directions, for reasons that are individually correct. The defect is that
A-153 was written against `MissReason` without checking which of its values a real request can produce,
and the ordering that made it unreachable is invisible from the ADR.

**The per-folder proposal is what surfaced this**, and it is also what fixes it — because the fix needs a
unit of authorisation coarser than a prompt name, which is exactly what ADR-0061 introduces.

## Decision

### 1. The rule is about the namespace, not about the name

**A request is forwarded if and only if the key is observe-enabled and the model string is not addressed
to a namespace this workspace uses.**

Two cases, and the first is the common one:

- **It carries no namespace at all.** `ModelName.parse` refuses it — no slash, or a shape outside
  A-021's. This is decided **syntactically, with zero reads**, before any table is touched. Every bare
  provider model name lands here.
- **It carries a namespace this workspace does not use.** `openrouter/…`, `meta-llama/…`. The namespace
  is checked against the workspace's namespace set — the union of `registry.folder` slugs and the
  namespaces observed on `prompt_property`, which `repository.list_folders` already computes. Not in
  the set, and not in the key's own `scope_namespaces`, means Prope has nothing here.

Everything addressed to a namespace the workspace **does** use resolves or refuses exactly as it does
today, for every key, observe-enabled or not. Unknown name, no release, unapproved pin, scope refusal:
four byte-identical 404s, unchanged.

### 2. Scope no longer pre-empts the question, because it no longer can

Under ADR-0061 a key's scope is a set of namespaces. A model string with no namespace has nothing to
check the scope against, so the ordering problem dissolves rather than being reordered around: the
syntactic case never reaches `may_resolve`, and the namespace case asks about the namespace, which is
the same unit the scope is expressed in.

`resolve_binding` keeps its current order for every request inside a workspace namespace. **No
additional read is added to the served path**, and the namespace set is cached beside the resolution
binding under ADR-0012's existing 30 s TTL — a set of folder slugs is small, and it is correct to
rebuild empty.

### 3. The key names where its observations land

`api_key` gains `observe_namespace text NULL` beside `observe_provider_config_id` (A-152), and
`observation.observation` gains `namespace text NOT NULL` written from it.

This is what closes ADR-0060's SR-2. That requirement says an observation has no owner and no access
level, so BR-01 has nothing to key on and visibility is workspace membership plus `prompt.create` — a
real widening with no fix available inside that module. With ADR-0061 there is now a container that
authority attaches to, and an observation lands in one:

- **Who may see the discovered prompts from one product is answered by one namespace grant**, through
  the same machinery as every other prompt in Prope. No rule of its own, no new permission, no special
  case in the inbox query.
- **Two products' discovered prompts do not mix.** Each key names its own namespace, and a key already
  has a `created_by`.
- **The default is closed.** `observe_namespace` is NULL like `observe_provider_config_id`, and a key
  cannot be put into observe mode without naming one — the API refuses the pair half-set, because a
  half-set pair is an observation with nowhere to go.

**Adoption must let the person choose a different namespace, and must not default to this one.** A-021
makes a model name immutable, so under ADR-0061 a prompt's access container never changes — which is a
security property everywhere else and a trap here: a prompt adopted into `discovered-checkout/` stays
there forever, inheriting the quarantine folder's grants for its whole life. The proposal route returns
a *suggested* model name (ADR-0060), and this decision fixes what it suggests: never the observation's
own namespace.

## Alternatives rejected

**Forward only the syntactic case, and never a namespaced one.** Strictly safer — zero reads, zero
enumeration surface, and A-116 untouched, because there is nothing to enumerate when the rule is
"does this string contain a slash". Rejected on coverage: OpenRouter, Together and Hugging Face model
ids are `vendor/model`, and they are a large and growing share of what a real integration sends. A
discovery feature blind to them would report an inventory that is wrong in a way nobody could see.

**Forward on `UNKNOWN_MODEL` per name, having reordered `resolve` ahead of the scope check.** The
smallest fix, and it is the one that leaks. An attacker holding a leaked key learns that
`finance/pricing` refuses and `finance/nothing` forwards — which is the registry enumeration A-116
exists to close, arriving through the observe door and charging the workspace a provider call for each
probe. Refused. Deciding at the namespace means `finance/nothing` is refused too, because `finance` is
a namespace this workspace uses, and the attacker learns nothing about names.

**Make observe a separate credential, so scope never applies.** Would sidestep the ordering entirely.
Rejected for ADR-0059's reason for rejecting a separate endpoint: the whole value is that a client
changes one line, and a second credential is a second thing to deploy.

## Consequences

- **A-153 is superseded by A-156** and marked so in its own file. The rule it stated is not merely
  narrowed — its premise was wrong, and a superseded assumption that reads like a narrowing is how the
  original mistake stays quotable.
- **ADR-0059's table is replaced.** Its five-row `MissReason` table describes a decision point real
  traffic does not reach; the rows about `NOT_PERMITTED`, `NO_RELEASE` and the two pin misses are
  **unchanged in effect** and now hold for a different and stronger reason — they are unreachable from
  the forwarded path by construction rather than by rule, because all four require a name inside a
  workspace namespace.
- **A-116 is deliberately weakened at the namespace boundary, and nowhere else.** A leaked key can
  discover which namespaces a workspace uses, by observing which strings forward. It cannot discover a
  prompt name, which is what the property was written to protect. Accepted in A-159 with the reasoning,
  rather than left as a gap somebody finds later — and the disclosure is bounded by what the key's own
  scope already implies under ADR-0061.
- **The gateway caches one more thing**, the workspace's namespace set, on the existing 30 s TTL. A
  newly created namespace is therefore not recognised for up to 30 s, during which a call to it is
  forwarded and observed rather than refused. That is the same staleness ADR-0012 already accepts for
  the released pointer, in the same direction: it costs one observation row somebody dismisses.
- **Two acceptance criteria in `gateway.lock.yml` are restated rather than added.** AC-16 asserts that
  a scope refusal and a withdrawn release both stay byte-identical 404s; both are now reached by names
  inside a workspace namespace, which is where the assertion has to be driven from for it to mean
  anything.
- **This is the second decision in two days to be corrected by looking at the code** — the first being
  `call-ledger.lock.yml`'s source vocabulary, stale since migration 0020. Both were found the same way,
  and neither was found by reading the document that was wrong.

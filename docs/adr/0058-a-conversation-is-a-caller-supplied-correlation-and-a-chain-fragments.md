# ADR-0058 — A conversation is a caller-supplied correlation, and a chain fragments rather than bridges

**Status**: Accepted
**Date**: 2026-08-18
**Decision**: user (asked and answered during the conversation-graph design)
**Module**: gateway (ingest) / call-ledger (storage) / prompt-registry (reader)
**Supersedes**: nothing. **Extends**: ADR-0055's per-prompt read to a second, grouped shape
**Related**: ADR-0018, ADR-0020, ADR-0030, ADR-0055, A-020, A-037, A-099, A-107, A-125, BR-01

## Context

A customer's application is not one prompt. A chatbot published to Prope typically registers a
system prompt, one or more guardrails, a tool-definition prompt and a handful of sub-agent prompts,
and one end-user conversation puts several of them through the gateway in sequence. Prope records
every one of those calls — and until now, records them as unrelated rows.

The `Log` tab can therefore answer *this prompt answered at 14:03* and cannot answer *this prompt was
the second of four steps in a chat that ended badly*. The second question is the one somebody
debugging a deployed application actually has, and no amount of staring at a flat list produces it.

Three facts constrain the answer.

**Nothing in an OpenAI-compatible request identifies a conversation.** There is no field, no header,
no convention. `user` is the nearest thing and it identifies a person, not a chat — one person with
two tabs open collapses into one graph.

**Grouping by key and time window is a guess.** `consumer_key_id` plus an N-second bucket needs no
change from the customer and is wrong the moment two end-users are served concurrently, which for a
deployed chatbot is the normal case rather than the exotic one. A graph assembled that way would be
confidently incorrect, which is worse than absent.

**A conversation spans prompts, and prompts are private by default.** This is the sharp one. ADR-0055
scoped the call-record read to a single prompt precisely so a list could not reveal that a private
prompt exists. A chain view walks straight back into that: the second node of somebody's chatbot may
be a guardrail owned by a colleague and visible to nobody else.

## Decision

**The caller declares the conversation. Prope stores the declaration, and reads it back per prompt.**

- **Two optional fields on the existing `prope` request object**: `conversation_id` groups the calls
  one conversation made; `parent_call_id` names the call a call followed from. Both are gated to
  `^[A-Za-z0-9_-]+$` and 64 characters at all three boundaries — the HTTP request, the broker
  envelope, and the URL path segment — because the value becomes an index key and a path segment.
  A caller that sends neither keeps the behaviour it has today and simply has no graph.
- **`parent_call_id` accepts the `chatcmpl-` prefixed form the gateway itself returns**, and is
  strict about everything else. The failure it prevents is silent: an unmatched parent is not an
  error, it is a second root.
- **Two nullable columns on `ledger.call_record`, and neither is a foreign key.** `parent_call_id`
  is a value for the reason `property_history.target_id` is: a parent can age out of retention while
  its child survives, and a constraint would force a delete the ledger may not perform.
- **The reader is `GET /prompts/{id}/conversations` and `.../{conversation_id}`, mounted by
  prompt-registry, behind `prompt.read`** — ADR-0055's placement and argument, unchanged. The graph
  route additionally requires that the named prompt actually took part in the conversation, so one
  `prompt.read` on a prompt you can see does not become a read of a conversation you cannot.
- **Nodes whose prompt the reader may not see are dropped, and their edges are not bridged.** The
  child of a removed node becomes a root. It is never re-parented onto its grandparent.
- **`hidden_count` is reported; nothing else about a hidden node is.** No id, no title, no owner, no
  revision, no position.
- **The response tells the caller its own `call_id`**, in the `x-prope-call-id`
  header and as the body's `id`. Without this the parent field is unfillable — see below.
- **Metadata only, still.** No node type has a field a body could arrive in. ADR-0018 is untouched.

## The response `id` is Prope's, not the provider's

`parent_call_id` names a `call_id` **Prope** generated, so there is exactly one
question that decides whether this feature exists at all: how does the caller find
out what the call it just made was called?

The first implementation had no answer. `ServedIdentity.stamp` set `model` and
`prope` and passed the provider's own `id` straight through, and no header carried
the call id, so a client copying the response `id` into the next request sent
something like `cmpl-1` — which the validator refuses by design. The field was
documented, validated, stored, indexed and queryable, and unfillable by anybody.

So the id is Prope's on **every** path, overwriting the provider's:

- **The body's `id` is `chatcmpl-<call_id>`.** It is the caller's only handle on
  the row Prope recorded, and a response whose id names a third party's record is
  a traceability claim that stops at the boundary — the one claim the product is
  for. The fallback path (`_completion`) had always answered with this shape, so
  passing the upstream id through on the ordinary path made one field mean two
  different things depending on whether the provider happened to be up.
- **On every streamed chunk, not only the first.** `prope` and `model` ride the
  first chunk, as they always have and as OpenAI's own streams do with `model`. An
  accumulating client keeps the *last* chunk it read, and a field that worked or
  not depending on which chunk survived would be worse than one that never worked.
- **`x-prope-call-id` carries it bare**, without the `chatcmpl-` prefix. That is
  the form Prope's own screens and logs show, so it is the form somebody pastes
  into a search box, and a streaming caller has the headers long before it has a
  body. `PropeRequestOptions` accepts either form back, which is what makes
  shipping both harmless rather than a third thing to get right.

Rejected: **putting `call_id` inside the `prope` body object instead.** It would
be a fourth place the same value lives and would not help a streaming caller
before the first chunk. The response `id` already exists, is already Prope's on
one path, and is the field every OpenAI client already reads.

## Why fragmenting is safe here, and a placeholder node would not be

Dropping a node leaves a visible discontinuity, and the obvious objection is that a discontinuity is
itself a disclosure — *something ran here that you cannot see*.

It is not, and the reason is a consequence of a separate decision: **the graph already omits every
step that did not pass through the gateway.** A tool execution, a retrieval, a regex guardrail and a
deterministic router all happen inside the customer's own process, where Prope never sees them. So a
gap between two boxes already has several innocent explanations, and a hidden private prompt is
indistinguishable from any of them. The client says so in words rather than leaving it to be
inferred.

A placeholder node — *restricted step* — would destroy exactly that ambiguity. It would confirm that
a prompt exists, that it is private, and where in a production chain it sits. That is the
existence-disclosure BR-01 closes as not-found, and it was rejected on those grounds.

`hidden_count` sits deliberately on the safe side of the same line. It is a count, not an identity:
it names nothing and cannot be refined by asking again. What it buys is the difference between a
fragmented graph and a *broken* one — without it, a reader seeing two disconnected chains cannot
tell whether their application misbehaved or their permissions did, and the first of those sends
them hunting for a bug that does not exist.

## Alternatives rejected

**Refuse the whole conversation unless every prompt in it is visible.** The strictest reading of
BR-01, and it discloses nothing at all. Rejected because `private` is the *default* access level, so
this would hide a great many conversations from people who legitimately own most of the chain, and
the refusal would give them no idea why.

**Bridge the edge over a dropped node.** Produces a connected, readable graph. Rejected outright: it
would draw *A called C* when the application called `A → B → C`. A graph whose whole purpose is to
show the shape of a chain must not misstate the shape, and a wrong picture is more expensive than an
incomplete one because nobody doubts it.

**Let the customer report non-gateway steps through a new ingest endpoint.** Would draw the complete
application trace, tool executions included. Rejected for the MVP: it is a new authenticated write
path and a new spam surface on a table that is append-only by privilege, and those rows would carry
no `prompt_id` — putting them outside the governance story entirely. This is the point at which
Prope stops being a prompt registry and starts being an APM, and A-012's *debuggable by one person*
clause is what says not yet.

**A workspace-wide conversation list.** Best discovery by a distance, and the natural place to spot a
broken chain you were not looking for. Rejected for ADR-0055's reason, which has not changed: a list
of every conversation names conversations that ran through private prompts.

**A CHECK constraint enforcing that a parent implies a conversation.** The application enforces it,
in `CallRecordDraft.__post_init__`, and a malformed record dead-letters. A CHECK would instead abort
the whole batch the drain is committing, taking a hundred innocent records down with one bad one, on
a path A-087 deliberately keeps off the response.

## Consequences

- **Customers must change one line** to get anything at all. This is the adoption cost and there is
  no way around it; a graph that appeared without their participation would be a guess.
- **A conversation is the customer's idea of a conversation.** Prope neither generates the id,
  checks it for uniqueness, nor attaches meaning to it. An application that reuses one id for its
  whole lifetime produces one enormous conversation, which is why the graph read is capped at 200
  nodes and reports truncation rather than silently showing a prefix.
- **`conversation_id` is customer-authored text on the ledger.** It is never emitted as a metric
  label — ADR-0030's cardinality bound would be unbounded by construction — and it is never logged.
- **Ordering is `(created_at, call_id)` as a row value.** A fan-out to parallel sub-agents routinely
  lands two calls in the same millisecond; A-125's argument applies here for the same reason it
  applies to history.
- **call-ledger gains no outbound edge.** The new read is prompt-registry → `call_ledger.seams`,
  the inbound direction ADR-0055 already established.
- **A caller that reads the response `id` sees a different value than before.** It
  is opaque in OpenAI's contract and no client is documented to correlate it with
  the provider, but it is a wire change and named here as one.

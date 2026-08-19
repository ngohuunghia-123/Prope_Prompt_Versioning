# prope-sdk

Call governed prompts through Prope's gateway from Python.

```bash
pip install prope-sdk
```

```python
from prope_sdk import Prope

prope = Prope(api_key="prope_key_...", base_url="https://prope.example.com")

answer = prope.chat(
    "support/refund-classifier",
    messages=[{"role": "user", "content": "Where is my refund?"}],
    variables={"tier": "gold"},
)

print(answer.text)
print(answer.version_id, answer.revision)   # exactly which revision served it
```

Your application names a prompt. It never holds the prompt.

## There is no `get_prompt`

This is the one thing to know about this package, and it is deliberate
(ADR-0065). No method returns prompt text, a template, or a revision body — not
for rendering, not for inspection, not behind a debug flag.

Other prompt-management SDKs fetch the template and let your process render it.
That shape costs three things:

- **Your process holds the prompt** — in memory, in logs, in error reports, in
  heap dumps. Prope's promise that a consuming product never holds a copy of the
  text becomes a description of one code path rather than a property.
- **What actually ran becomes unverifiable.** Once your code holds the template
  it can append to it, and Prope can only record what was *fetched*, not what was
  *used*. `version_id` would stop meaning "this revision produced this call".
- **Release control becomes advisory.** A fetched template can be cached or held
  for a month, so withdrawing a release stops affecting anything already running.

If you want to read a prompt body, read it in the Prope web application, as a
person holding `prompt.read`. A consumer key is not a reader.

## Chains that thread themselves

A conversation is how Prope draws a graph of a multi-step agent. Threading it by
hand is correct and tedious — every step is a place to pass the wrong parent.

```python
with prope.conversation() as chain:
    plan   = chain.chat("support/planner", messages=history)
    answer = chain.chat("support/answer",  messages=history + [{"role": "assistant", "content": plan.text}])
```

Step one is a root; every later step names the one before it. Open any of those
prompts in Prope, go to **Logs**, and the chain is drawn there.

For a fan-out where each branch should name the same parent rather than each
other:

```python
chain = prope.conversation()
draft = chain.chat("support/draft", messages=history)

for lens in ("correctness", "tone", "policy"):
    chain.branch().chat(f"support/critic-{lens}", messages=[...])
```

Pass your own id when you have one — a session or thread id your application can
look up is worth more than a value only Prope has ever seen:

```python
prope.conversation(session.id)
```

## Streaming

```python
for chunk in prope.stream("support/answer", messages=history):
    print(chunk.text, end="", flush=True)
```

Every chunk's `text` concatenates to the answer; frames carrying only identity or
usage yield `""` rather than needing to be filtered.

## Async

Identical surface, awaited.

```python
from prope_sdk import AsyncPrope

async with AsyncPrope(api_key=..., base_url=...) as prope:
    answer = await prope.chat("support/refund-classifier", messages=history)
```

## Pinning a revision

```python
prope.chat("support/answer", messages=history, pin="v3")
```

Only an **Approved** revision can be pinned. The gateway refuses anything else
with the same not-found it gives an unknown prompt.

## What this key can call

```python
prope.models()   # ['support/refund-classifier', 'billing/invoice-explainer']
```

Both scopes unioned: prompts granted by name, and every released prompt in a
folder the key was granted. An empty list is a scope problem, not a release one.

## Errors

Typed, and carrying the gateway's machine `code` rather than a message you have
to parse.

```python
from prope_sdk import ModelNotFound, MissingVariable, GatewayUnavailable

try:
    answer = prope.chat("support/answer", messages=history)
except MissingVariable as missing:
    log.error("the revision now needs %s", missing.name)
except ModelNotFound:
    ...          # unknown, unreleased, or out of this key's scope — see below
except GatewayUnavailable:
    ...          # Prope could not be reached at all
```

`ModelNotFound` says less than it appears to, on purpose. It is byte-identical
whether the prompt does not exist, has no release, is outside this key's scope,
or is pinned to a revision that was never approved — so that a leaked key learns
nothing by probing. Do not write code that infers which; check the key's scope
first, since that is the one a person can fix without a release.

**Nothing is retried and nothing is swallowed.** An SDK that quietly answers when
the governed path is unavailable is a way for an ungoverned answer to reach
production. Retry policy is yours.

## Migrating an existing application

Do not do it by hand. The `prope-migrate` skill (ADR-0066) reads your repository,
proposes a manifest of every prompt it found with its real variable names, and —
once a person has reviewed it — registers them and rewrites the call sites into
`prope.chat(...)` as a diff you review like any other change.

It never approves and never releases. Registered revisions land as `Draft`, and a
person approves them one at a time. That tedium is the control working.

Afterwards, point an observing key at the migrated application for a week:
anything still forwarding is a prompt the scan missed (ADR-0064).

## Notes

- **The package is `prope_sdk`, not `prope`.** Prope's own service package is
  `prope`. If you prefer the shorter name: `import prope_sdk as prope`.
- **`base_url` is an origin.** `https://prope.example.com`, not
  `.../v1` — though a trailing `/v1` is tolerated and stripped, because it is the
  most common configuration mistake in every OpenAI-compatible client.
- **No `system` messages.** The released revision carries the system prompt. The
  SDK refuses one locally, before the request leaves, and names the index.
- **No dependency on `openai`.** One HTTP client, one request shape.
- **Local steps** — a tool that raised, a retrieval that returned nothing — are
  not in this version. Their storage is an open question (OQ-154), and shipping a
  method that silently dropped them would be worse than not having one.

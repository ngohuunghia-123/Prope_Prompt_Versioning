---
name: prope-migrate
description: >
  Migrate an application's hardcoded LLM prompts into Prope. Scans the repository
  for prompts, writes a reviewable manifest, and — after a person has reviewed it —
  registers them as Draft revisions and rewrites the call sites to use the Prope
  SDK. Never uploads without an explicit second act, never approves, never
  releases, never commits. Use when a codebase keeps its system prompts in source
  and the team wants them governed.
---

# Migrating prompts into Prope

You are running inside **someone else's repository**. Your job is to find the
prompts their application holds, describe them accurately enough for a person to
make decisions about, and — only once that person has decided — move them.

Read this whole file before you touch anything.

## The rule that matters more than the rest

**You propose. A person performs.**

There are two acts in this process that change something outside your working
directory: uploading prompts to Prope, and modifying the application's source.
Neither happens unless a human being explicitly asks for it *after* reading what
you found. Phase 1 and 2 are the default; phases 3 and 4 require someone to say
so, each time.

This is not caution for its own sake. A prompt's `namespace/name` is **immutable
once created** — it is what a consuming product calls, and Prope has no rename.
A prompt filed in the wrong folder is filed there for life, and the folder is
also its access container, so a bad guess is a permanent access mistake. You are
not able to make that decision well. The person reviewing the manifest is.

## Phase 1 — Scan (read only)

Find every place this application sends a prompt to an LLM. Look for:

- **String literals reaching an LLM client** — arguments to
  `openai.chat.completions.create`, `anthropic.messages.create`,
  `client.responses.create`, LangChain/LlamaIndex prompt objects, or whatever
  wrapper this codebase uses. Find the wrapper first; most codebases have one.
- **Messages with `role: "system"`** — the highest-signal pattern there is.
- **Prompt constants and modules** — `PROMPTS = {...}`, `prompts.py`,
  `prompts/*.txt`, `*.j2`, `*.md` files loaded at runtime.
- **Assembly sites** — a prompt built by concatenation, `.format()`, f-strings,
  or `textwrap.dedent` across several functions. These matter most and are
  easiest to miss: what a proxy would see is the *rendered* result, and what you
  can see is the *template*, which is the thing worth registering.

Write nothing outside your output directory. Make no network calls. Do not
modify a single file in the repository during this phase.

### Record what each call site is written in

Put the language or runtime on every source you record — `python`,
`typescript`, `browser`, `go`. It is one word and it decides whether phase 4 can
happen at all: **the SDK is Python.** A prompt whose only call site is browser
JavaScript, a Go service, or a Rails app can be scanned, registered and governed,
and cannot be rewritten to call Prope through the SDK.

Say so in phase 2, in the row's warnings and in the manifest notes, loudly enough
that nobody authorises phase 3 without knowing it. Registering is irreversible in
the way that matters — `namespace/name` cannot be changed or deleted — so a
reviewer who discovers the mismatch at phase 4 discovers it after the permanent
decision, not before it.

### Extracting the body

Prope stores a prompt as **canonical XML**: a flat sequence of blocks, no
nesting, no attributes, no text outside a block. The allowed blocks are exactly:

`system` · `context` · `instructions` · `output_format` · `examples` · `constraints`

A plain-text prompt becomes canonical by being split into the blocks it already
implicitly has:

```xml
<system>You classify incoming email for a logistics desk.</system>
<instructions>Read the message and return one label: quote, claim, tracking, or other.</instructions>
<output_format>The label alone, lower case, nothing else.</output_format>
```

That example is deliberately unlike anything you are likely to be looking at.
Do not treat it as a target shape or a length to aim for: the number of blocks
and the amount of text are whatever the original prompt actually has.

Rules for the split:

- **Do not rewrite the prompt.** Reorganise it into blocks and change nothing
  else — no improving the wording, no fixing the grammar, no tightening. The
  registered revision must be what the application is running today, or the first
  thing the migration does is change behaviour nobody asked to change.
- If a prompt genuinely has only one part, one `<system>` block is a complete and
  correct canonical body.
- Escape `&`, `<` and `>` in the text.
- Never emit `<!DOCTYPE` or `<!ENTITY`; both are rejected.
- The whole body must be under 32,768 characters.

### Keep the original

Record the prompt **exactly as it appears in the source** as well as the
canonical version: `original_body`, `original_format` (`txt`, `markdown`, `json`,
`yaml`), and `original_filename`. Not a tidied copy — the text, with its
whitespace and its wording, before you touched it.

Prope stores both, because reorganising a prompt into blocks is a conversion
performed by a model, and the reviewer's real question is *is this the same
prompt?* A row that carries only the canonical XML and a file path makes them go
and find out; a row that carries both answers it. It also outlives the source:
the file gets edited, the branch gets deleted, and the stored original becomes
the only surviving copy of what the application was actually running.

Where the source was already canonical XML, leave `original_format` at `xml` and
omit `original_body` — nothing was converted.

### Extracting the variables

Prope's placeholder syntax is `{{name}}`. Convert whatever the application uses:

| in the source | in the canonical body |
|---|---|
| `f"Today is {today}."` | `Today is {{today}}.` |
| `"Hello {name}".format(...)` | `Hello {{name}}` |
| `"Hello %s" % user` | `Hello {{user}}` — **and flag it**, since the name is not in the source |
| `Template("$x").substitute` | `{{x}}` |

**Use the real identifier from the source.** This is the single biggest advantage
you have over watching production traffic, which can only infer `var_1`, `var_2`
by diffing. When the source does not carry a name — positional `%s`, an index
into a tuple — say so in the manifest rather than inventing one.

### Proposing a name

Propose `namespace/name`; do not decide it.

- Lower case, digits, dot, dash, underscore. `namespace/name`, one slash.
- Derive the **namespace** from where the prompt lives in *their* codebase — the
  service, package or bounded context it belongs to. Do not import Prope's own
  vocabulary; this is their namespace, in their words.
- Derive the **name** from what the prompt does, in their terms.
- Where you are unsure, say so in `name_confidence`. A reviewer skims a manifest
  and stops on the rows you flag.

## Phase 2 — Manifest (the deliverable)

Write one file: `.prope/manifest.json`, conforming to `manifest.schema.json`
next to this skill.

**Then stop.** A run that ends here is a complete, successful run. Report what
you found, name the rows you were unsure about, and tell the person the file is
ready to review. Do not offer to upload it in the same breath; let them read it.

Before writing, ensure `.prope/` is git-ignored — append it to `.gitignore` if it
is not, and say that you did. The manifest is a plaintext inventory of every
prompt the product uses. The bodies were already in the repository, so this is
not a new disclosure of the content; it is a new disclosure of the **collection**,
which is exactly the artefact an attacker would otherwise have to assemble. A
migration that leaks prompts into git history has moved the problem somewhere
worse, because git history is not deletable the way a Prope row is.

## Phase 3 — Register (only when asked)

Run `register.py` against the reviewed manifest. It creates a prompt and a first
revision for each entry.

```bash
python register.py --manifest .prope/manifest.json --base-url https://prope.example.com
python register.py --manifest .prope/manifest.json --base-url https://prope.example.com \
    --provider-config-id prv_... --upstream-model gpt-4o-mini --apply
```

Without `--apply` it prints what it would create and exits. That is the default
because the flag protecting a policy has to be the one you type to *bypass* it,
not the one you must remember to type to honour it.

### The provider binding is not optional in practice

A revision names a provider configuration and a model together, or neither. Prope
refuses one without the other, and a revision that binds **neither** registers
happily, can be approved, can be released — and then fails every call with
`provider_configuration_unusable`. The failure surfaces at the first real
request, which is to say after the migration looked like it worked.

So the reviewer has to supply `--provider-config-id`. A repository scan cannot
find it: it is workspace state, not repository state, which is why it is a flag
and not a manifest field. The id is on the provider's row in the web
application's settings. Where a manifest row records no `upstream_model` —
common, because plenty of applications take the model name from configuration
rather than from source — `--upstream-model` binds them all to one, and whoever
approves each revision can change it before releasing.

`--conversion-model` names the model that did the reorganising, and is required
as soon as any row records a conversion. It is what stops a revision saying "an
LLM wrote this XML" without saying which one.

`register.py` refuses the whole run rather than half-registering it, and says
which rows are the problem. Do not work around that by deleting `upstream_model`
from the manifest: the model an application is running today is a fact about the
migration, and dropping it to get past a check throws it away.

**Revisions land as `Draft`. You do not approve and you do not release.** Not
with a flag, not on request, not "just for the staging workspace". A bulk import
that auto-approved would put every prompt in this repository into production
unreviewed, with one recorded actor — which is the exact outcome Prope's approval
chain exists to prevent. If the team wants forty prompts live today, the price is
forty approvals in the web application, one at a time, each with a person's name
on it. That tedium is the control working.

After registering, tell the person plainly: nothing is callable yet. Each prompt
needs a review and a release before the rewritten code will resolve it.

**Re-running is safe.** A run that fails partway leaves the prompts it already
created, and `namespace/name` is immutable with no delete — so a second run
adopts what the first one made and adds a revision to it rather than refusing
with a name clash. That is also how you correct a binding: fix the flags, run
again, and each prompt gains a new Draft revision. It is never how you correct a
name, because you cannot.

## Phase 4 — Rewrite (only when asked)

Replace each literal with an SDK call. Leave the result as **uncommitted changes
or a pull request**. Never commit. Never push. Never deploy.

```python
# before
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": f"You are Acme Support. Today is {today}."},
        {"role": "user", "content": question},
    ],
)
text = response.choices[0].message.content

# after
from prope_sdk import Prope
prope = Prope(api_key=os.environ["PROPE_API_KEY"], base_url=os.environ["PROPE_BASE_URL"])

answer = prope.chat(
    "support/front-line",
    messages=[{"role": "user", "content": question}],
    variables={"today": today},
)
text = answer.text
```

Four things to get right:

1. **The `system` message goes away entirely.** The released revision carries it.
   Leaving it in is the most common migration error, and the SDK refuses it
   locally with the message index — but a reviewer should never see that, because
   you should have removed it.
2. **The model name is the prompt**, `namespace/name`, not `gpt-4o-mini`. The
   provider model is bound to the revision, chosen by whoever approves it.
3. **Interpolation becomes `variables=`, and this is the step that breaks apps.**
   See below. The f-string disappears; the value it interpolated is passed as
   data — *and the code that computed that value has to survive*.
4. **Build the client once**, at module scope or in the application's DI
   container — not per call.

### Every variable must be supplied at every call site

This is the most common way a migration ships broken, and it fails on the first
request rather than in an edge case.

A body registered as `Today is {{today}}.` requires `today` from **every** caller,
forever. If the rewrite drops it, the app answers `missing_variable` to every
user immediately — a prompt that worked before the migration and does not work
after it, which is the one outcome a migration may not produce.

The manifest already tells you what to pass: each variable's `source_expression`
is the expression the code interpolated, recorded verbatim in phase 1 for exactly
this moment. Move it, do not replace it.

```python
# before — the app computes the value itself
today = date.today().isoformat()
messages = [{"role": "system", "content": f"You are Acme Support. Today is {today}."}, ...]

# after — the same expression, now passed as data
answer = prope.chat(
    "support/front-line",
    messages=[{"role": "user", "content": question}],
    variables={"today": date.today().isoformat()},
)
```

What that must never become:

- a constant baked in at rewrite time — `{"today": "2026-08-19"}` is wrong
  tomorrow and wrong silently;
- a value a human is expected to type;
- an omission on the grounds that the variable "usually has a default". There
  are no defaults. A missing variable is a refusal, not a blank.

**Check it before you stop.** For each rewritten call site, the set of names in
`variables=` must equal the set of `{{...}}` in that prompt's registered body.
Not a subset. If a call site genuinely cannot produce a value for one of them,
the split was wrong: that text was part of the prompt, not a variable, and the
row needs fixing before the rewrite — which means a new revision, since a
released one is immutable.

For a multi-step chain, use a conversation so the steps thread themselves:

```python
with prope.conversation(session_id) as chain:
    plan = chain.chat("support/planner", messages=history)
    answer = chain.chat("support/answer", messages=history)
```

Pass the application's own session or thread id when it has one. A graph keyed by
something the application can look up is worth more than one keyed by a value
only Prope has ever seen.

**Do not change behaviour while you are here.** No refactoring beyond the call
site, no improving the prompts, no adding retries. A migration diff a reviewer
cannot read is a migration that does not land.

### When the call site is not Python

Stop and say so. Do not import `prope_sdk` into a language that cannot run it,
and do not build a service to bridge the gap — a new backend route, a translation
between the SDK's types and whatever the client already parses, and a decision
about who now holds the API key are all well beyond a call site, and all of them
are a person's call.

Report the two honest options and let somebody choose:

1. **A bridge**, if this application already has a server the prompts could move
   behind. That is new architecture, not a migration, and it is scoped separately.
2. **The gateway directly.** Prope's gateway is OpenAI-compatible, so an existing
   client keeps its own HTTP call and changes two things: `model` becomes
   `namespace/name`, and the `system` message goes away because the released
   revision carries it. Variables travel in a `prope` object alongside `messages`.
   No SDK, no new dependency, and it works from any language — what it gives up
   is the SDK's typed refusals and automatic conversation threading.

## Phase 5 — Verify (tell them about it)

You cannot know what you missed. Prompts assembled at runtime, loaded from a
database, or living in a service nobody pointed you at are invisible to a reader
and obvious to the gateway the first time they run.

So after the rewrite ships, an **observing key** pointed at the migrated
application answers the question directly: anything still forwarding is a prompt
the scan did not find. Tell the person this, and tell them the migration is
complete when that punch list is empty — not when your scan reported success.

## What to report at the end of each phase

Say what you did, what you found, **what you were unsure about**, and what the
next act would be — naming the person who has to perform it. Never say a
migration is complete; say what phase finished.

A false positive in your manifest is a row a reviewer deletes. A false negative
is caught in phase 5. Neither reaches production, which is why the phases are
split where they are — so be thorough rather than conservative in phase 1, and
flag rather than guess in phase 2.

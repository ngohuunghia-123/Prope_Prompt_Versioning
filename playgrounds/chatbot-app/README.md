# Chatbot app

A mock product — "Acme Support" — in the two states a real product is in before
and after it adopts Prope.

**`index.html`, the page you get by default, is the *before*.** It is an ordinary
chatbot: its system prompts are hardcoded in its own source, it names a model at
the provider, and it has never heard of Prope. The only thing tying it to Prope
is the pair under **Settings** — a base URL and an API key. That is the whole
integration, and it is the point: if getting a product's prompts into Prope cost
more than editing the two lines it already edits to point at an OpenAI-compatible
endpoint, no team with prompts in production would ever pay it.

**`integrated.html` is the *after*** — the same product calling released prompts
by name, holding no prompt text, threading agent chains into one conversation
graph. That is the destination.

> **Amended 2026-08-19 (ADR-0063, ADR-0064).** Pointing an unmodified app at the
> gateway was once Prope's adoption story. It is not any more, and this playground
> means something different because of it. An observation delivers none of the four
> non-negotiables — no approval, no revision, nothing editable, and the prompt still
> ships from the product's own source — so a cheaper road to that room was still a
> road to a read-only room.
>
> Integration is now a **migration**: the SDK (`sdk/python`) plus an agent-assisted
> rewrite of the customer's repository (`skills/prope-migrate`). What `index.html`
> demonstrates is therefore no longer "adoption in one line". It is the **audit**:
> an application the migration has not been run against, whose traffic the gateway
> can still describe. Run the migration, ship it, then point an observing key at the
> result for a week — anything still forwarding is a prompt the scan missed. The
> migration is complete when the inbox is empty, not when the scan says so.

```powershell
cd playgrounds\chatbot-app
python server.py
```

Open <http://localhost:8090>, paste the gateway address and an API key under
**Settings**, press Save. Nothing to install, no environment variables, no
arguments — all configuration is in the page.

## The app that has not adopted Prope

`index.html` behaves like every chatbot that has not adopted Prope yet:

- its system prompt comes from **its own source**, in `APP_PROMPTS` near the
  bottom of the file, where a real product keeps it — and the sidebar shows you
  those bodies, so you can see what Prope was never given;
- it names a model at the **provider** — `gpt-4o-mini`, not
  `acme-support/planner` — typed in, because there is no registry to pick from.
  It never calls `GET /v1/models`;
- it sends a `system` message, which the Prope-native path refuses outright;
- it sends **no `prope` block at all**: no variables, no conversation id, no
  parent call id, no pin. The **Last request** panel shows the exact body on the
  wire so that absence is visible rather than claimed.

Point that at Prope's gateway with an **observing key** and the call is forwarded
to the provider behind that key and answered normally, while Prope files what it
saw (ADR-0059, ADR-0060). The product is not modified, is not redeployed, and
cannot tell — the response is byte-identical to the provider's, with no marker of
any kind, because a legacy app that could detect observation would start behaving
differently once it knew. The `no prope block sent` tag under an answer is this
page reporting what **it** did, not something it read off the reply.

Three personas ship with it, and the mix is deliberate: `support agent` and
`billing specialist` interpolate today's date into every call, `ticket summariser`
does not. Send several messages on one persona and the sighting count climbs on a
**single** observation group — a body that differs only where a variable was
interpolated is the same prompt, and the date comes back as an inferred variable
rather than splitting the group per day.

### Trying it end to end

```powershell
python seed.py --list-providers                  # pick a provider_config_id
python seed.py --provider prv_... --observe-key  # mint the observing key
python server.py                                 # then open localhost:8090
```

Paste that key under **Settings**, type the provider's own model name, and send a
few messages — switching persona partway. Then:

```powershell
python seed.py --observations
```

Each group prints its sighting count, the window it was seen over, the upstream
model names, the variables inferred from the body, and an excerpt. What to check:

- **one group per persona**, not one row per message;
- the date-carrying personas list an inferred variable; the summariser lists none;
- `status` is `open` until somebody adopts or dismisses the group.

Observations are filed in the `observed` folder, which nobody has been granted.
That is ADR-0061 working as intended — an undiscovered prompt is private by
default, and whoever triages the inbox is granted **that one folder** rather than
the registry.

**An observation is not a prompt, and it does not get a name.** It is a
fingerprint group with a body, a sighting count and a suggested name, sitting in
a folder. Nothing in the registry has been created, no revision exists, and
nothing is callable. Adopting a group is what turns it into a prompt — with an
owner, a revision chain and a recorded approval — and adoption is an act a person
performs, which is non-negotiable #1 holding at the one place it would be most
convenient to skip.

There is no inbox screen in the web app yet, which is why `--observations` exists.

## After adoption: `integrated.html`

Two modes, both of them the consuming side of the core value — **the product
names a prompt and never holds its text**, and every answer comes back stamped
with the exact revision that served it.

**One prompt** is the simple case: one message, one gateway call, one released
revision. Streaming, pinning and variables all live here.

**Agent chain** is a ReAct agent built the way a real chatbot is — out of several
published prompts rather than one. A single customer message goes through:

```
input guard ──► planner ──┬──► retriever ──► [ help-centre search, in this app ]
                          ├──► specialist  (a sub-agent, when the planner escalates)
                          └──► planner ──► answer ──► output guard
```

Six roles, six released prompts, six gateway calls, all threaded into **one
conversation** — which is exactly what Prope's conversation graph is for. Send a
message, then open any of those prompts in Prope, go to **Logs**, and the chain
is drawn there as a graph.

The grey rows in the step trace are the tools running *in this page*: the
help-centre search and the order lookup. They never touch Prope, which is why
they leave a gap in the graph rather than a node. That gap is the honest shape of
the thing — Prope sees the prompts it serves and nothing else.

## Getting six prompts to run it against

`seed.py` registers, releases and keys all six in one go:

```powershell
python seed.py --list-providers            # pick a provider_config_id
python seed.py --provider prv_... --key    # register, release, and mint a key
```

It uses the same `prope_session` cookie the web app does and reads
`ADMIN_SESSION_TOKEN` from the repository `.env`, so there is usually nothing to
set. `--key` prints a consumer key scoped to the six model names — copy it
immediately, it is shown once.

**It approves its own prompts**, through `approve-and-release` with an
acknowledgement that names the script. Prope records self-approval rather than
refusing it, and the history will say plainly that no second person looked. Point
it at a development workspace and nothing else.

The bodies live in `prompts/` as canonical XML and can be pasted into Prope by
hand instead — six prompts under the `acme-support` namespace:
`input-guardrail`, `planner`, `retriever`, `billing-specialist`, `answer-writer`,
`output-guardrail`. `seed.py` registers them **workspace-visible**, deliberately:
the conversation graph drops steps whose prompt the reader may not see, and a
demo whose chain silently fragments teaches the wrong lesson about a control that
is working exactly as designed.

Already have prompts of your own? **Auto-assign** matches them by name, and every
role can be pointed anywhere by hand. A role left on *skip* is skipped and the
chain runs shorter — with only an answer prompt assigned, agent mode is one call,
which is a fine way to see the wiring before committing six prompts to it.

## What `integrated.html` demonstrates

Everything in this section is the adopted product. The legacy page does none
of it, which is the comparison worth having side by side.

- **`GET /v1/models`** fills the model picker and the role pickers. The list is
  what this key may resolve, so both are the key's scope made visible.
- **`POST /v1/chat/completions`** carries `user` and `assistant` turns and never a
  `system` message. The gateway refuses one with `system_message_not_allowed`,
  because the released revision *is* the system prompt.
- **The pin box** appends `@v3` to the model name and asks for that revision
  specifically. Unpinned resolves whatever is currently released, which is what
  makes a rollback take effect here with no redeploy.
- **Variables** are sent as `prope.variables`. When a revision needs one you have
  not supplied, the gateway answers `missing_variable` and names it in `param`;
  the panel then offers exactly that row.
- **`prope.conversation_id`** goes out with every call in both modes, and
  **`prope.parent_call_id`** names the step each step followed from. Prope
  generates neither — nothing in an OpenAI-compatible request identifies a
  conversation, so the caller has to say. That is the one line a real integration
  has to add to get a graph.
- **`x-prope-call-id`** is how the next step knows what to name as its parent. It
  comes back on every response, alongside the same value as the body's `id` in
  OpenAI's `chatcmpl-` clothing; the gateway accepts either form back.
- **Every answer is stamped** with the model, revision number, `version_id`,
  `call_id`, whether it was pinned, and whether a fallback answer was served.
- **The same calls appear in Prope** under each prompt's Logs tab, attributed to
  this key's name, and grouped under the conversation id shown in the sidebar.
  That round trip is the traceability claim, end to end.

Streaming is on by default in one-prompt mode and can be switched off to compare
the two shapes. With it on the request asks for `stream_options.include_usage`,
which is why token counts appear on the stamp. **Agent mode never streams**: each
step's output decides the next one, so there is nothing to stream into, and the
checkbox is disabled rather than quietly ignored.

## Sending it to a teammate

Two ways, both fine for a dev environment.

- **Send the folder.** `index.html`, `integrated.html` and `server.py` must sit
  next to each other.
  They run `python server.py` and fill in Settings themselves.
- **Let them use yours.** `python server.py --host 0.0.0.0` and send the link
  `http://<your-ip>:8090`. They still type their own key, since it is stored per
  browser.

## Getting a key

Sign in to Prope, open **API keys**, create one for this app, and copy the
plaintext — it is shown once and cannot be recovered afterwards. Give the key a
scope that includes every prompt you want to call, and make sure each has a
released revision; a key that resolves nothing loads an empty model list, which
the page says out loud. `seed.py --key` does all of this for the six demo
prompts.

The key is kept in the browser's `localStorage` and sent with each request.
**Show key** reveals it, **Forget** clears it. That is a development
convenience — a real product keeps its key on a server, out of the client.

## Why there is a server for a single page

Prope configures no CORS anywhere — the SPA and the API share one origin, which
is what lets the `SameSite=Lax` session cookie work with no CSRF token (ADR-0029,
ADR-0052). A page opened straight from `file://` fails its preflight against
`/v1/chat/completions`; the browser blocks it before Prope is even asked. Checked
rather than assumed: an `OPTIONS` to that path returns a bare 405.

`server.py` is the smallest thing that fixes that without touching Prope. It
serves the page and forwards `GET /v1/models` and `POST /v1/chat/completions` —
nothing else, so it stays a demo app rather than an open relay. It holds no
configuration of its own: the gateway address and key ride along on each request
as `x-prope-base-url` and `Authorization`.

## Which address to point it at

The gateway shares the SPA's origin, so a hosted deployment needs no port and no
path: `https://prope.example.com`, origin only. The page appends `/v1/models` and
`/v1/chat/completions` itself, so a base URL ending in `/v1` asks for `/v1/v1`.

**If that address answers with an HTML block page instead of JSON**, something in
front of Prope refused the call — a CDN challenge, a WAF rule, a bot filter. It
is not Prope: every Prope refusal is JSON. The relay now says so, and repeats the
ray ID or request ID from the block page, because that is the only thing that
identifies which rule fired.

The fix is on the filter, not here: **exempt `/v1/*` from bot protection**, scoped
to that path and nothing else. `deploy/README.md` §1.7 has the rule and the two
things not to do with it. Every consumer benefits, not just this relay — an SDK on
httpx or undici carries the same signature and hits the same wall.

Relevant but not sufficient: this relay identifies itself as
`prope-chatbot-playground/1.0` rather than the `Python-urllib/3.13` that
Cloudflare's Bot Fight Mode blocks by name. An honest name is allowlistable, which
a spoofed browser string would not be. It is a second lever, not the fix — it
would only ever unblock this one client.

## What it is not

Not a supported client, not part of the deployed stack, and a development toy: it
trusts whatever address the page tells it to call. It renders answers as plain
text — no Markdown, no HTML — so model output cannot inject anything into the
page. Interface language is English, matching the sibling playgrounds; ADR-0053's
Vietnamese-only rule governs Prope's own UI, not a mock third-party product.

The agent is a demonstration and not a framework. Its planner loop is capped at
three turns, its retrieval is eight hard-coded help-centre articles ranked by word
overlap, and its parsing of what each prompt said is deliberately forgiving —
anything it cannot read as a tool call is treated as *enough, go and answer*, so
pointing a role at a prompt that was written for something else produces a short
chain rather than an error in front of the customer.

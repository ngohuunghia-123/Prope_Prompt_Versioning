# Chatbot app

A mock product — "Acme Support" — that calls a released prompt through Prope's
OpenAI-compatible gateway. It shows the consuming side of the core value: **the
product names a prompt and never holds its text**, and every answer comes back
stamped with the exact revision that served it.

```powershell
cd playgrounds\chatbot-app
python server.py
```

Open <http://localhost:8090>, paste the gateway address and an API key under
**Settings**, press Save. Nothing to install, no environment variables, no
arguments — all configuration is in the page.

## Sending it to a teammate

Two ways, both fine for a dev environment.

- **Send the folder.** `index.html` and `server.py` must sit next to each other.
  They run `python server.py` and fill in Settings themselves.
- **Let them use yours.** `python server.py --host 0.0.0.0` and send the link
  `http://<your-ip>:8090`. They still type their own key, since it is stored per
  browser.

## Getting a key

Sign in to Prope, open **API keys**, create one for this app, and copy the
plaintext — it is shown once and cannot be recovered afterwards. Give the key a
scope that includes the prompt you want to call, and make sure that prompt has a
released revision; a key that resolves nothing loads an empty model list, which
the page says out loud.

The key is kept in the browser's `localStorage` and sent with each request.
**Show key** reveals it, **Forget** clears it. That is a development
convenience — a real product keeps its key on a server, out of the client.

## What it demonstrates

- **`GET /v1/models`** fills the model picker. The list is what this key may
  resolve, so the picker is the key's scope made visible.
- **`POST /v1/chat/completions`** carries `user` and `assistant` turns and never a
  `system` message. The gateway refuses one with `system_message_not_allowed`,
  because the released revision *is* the system prompt.
- **The pin box** appends `@v3` to the model name and asks for that revision
  specifically. Unpinned resolves whatever is currently released, which is what
  makes a rollback take effect here with no redeploy.
- **Variables** are sent as `prope.variables`. When a revision needs one you have
  not supplied, the gateway answers `missing_variable` and names it in `param`;
  the panel then offers exactly that row.
- **Every answer is stamped** with the model, revision number, `version_id`,
  whether it was pinned, and whether a fallback answer was served — read from the
  `x-prope-*` response headers and the `prope` object in the body.
- **The same call appears in Prope** under that prompt's Logs tab, attributed to
  this key's name. That round trip is the traceability claim, end to end.

Streaming is on by default and can be switched off to compare the two shapes.
With it on the request asks for `stream_options.include_usage`, which is why
token counts appear on the stamp.

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

## What it is not

Not a supported client, not part of the deployed stack, and a development toy: it
trusts whatever address the page tells it to call. It renders answers as plain
text — no Markdown, no HTML — so model output cannot inject anything into the
page. Interface language is English, matching the sibling playgrounds; ADR-0053's
Vietnamese-only rule governs Prope's own UI, not a mock third-party product.

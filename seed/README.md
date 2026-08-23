# `seed/` — import the prompt library into a workspace

Converts every prompt in [`playgrounds/prompts/`](../playgrounds/prompts) to
canonical Prope XML and inserts it into a real workspace ("company") as a prompt
plus a `Draft` revision.

- **`converter.py`** — deterministic, offline `txt → canonical XML`. No LLM, no
  network. It reuses the product's own serializer/validator
  (`prope.prompt_conversion.domain.serialize_agent_output`,
  `prope.canonical_prompt.validate_canonical_xml`), so the stored bytes are
  canonical by construction. All 359 sample prompts convert and validate.
- **`seed_prompts.py`** — authenticates with an email + password, resolves the
  workspace, and writes each prompt through the real command layer
  (`prompt_registry.create_prompt` / `create_revision`) inside the
  `workspace_transaction` tenant seam.

## Why revisions stay `Draft`

Prope's core guarantee is that *no prompt reaches production without a recorded
human approval*. The seed therefore never approves or releases anything — every
imported prompt lands as an active prompt with one `Draft` revision. Reviewing,
approving, and releasing remain human steps in the app.

## Prerequisites

1. The stack is running: `docker compose up -d` (see the repo README / compose
   files). Postgres is **not** exposed to the host, so the seed runs inside the
   compose network.
2. **An account already exists, and it is in exactly one workspace.** The seed
   authenticates an existing user; it does not create one, and it does not choose
   a workspace. Since ADR-0056 registration creates an account and nothing else,
   so signing up is two steps — register, then create or join a workspace on the
   chooser the app shows immediately afterwards (or `POST /api/v1/workspaces`
   with the session cookie that response set). An account in no workspace, or in
   several, exits with a message saying so rather than having one picked for it.

   Create the account by signing up in the app, or via the API:

   ```bash
   curl -X POST http://localhost:8080/api/v1/auth/register \
     -H 'Content-Type: application/json' \
     -d '{"display_name":"Owner","email":"owner@acme.com","password":"your-password"}'
   ```

## Run it

Run as the `prope_app` role the `app` service already uses, mounting this folder
and the prompts into a one-off container:

```bash
docker compose run --rm \
  -v "$(pwd)/seed:/work/seed" \
  -v "$(pwd)/playgrounds:/work/playgrounds" \
  -w /work \
  app \
  python seed/seed_prompts.py --email owner@acme.com --password 'your-password'
```

PowerShell (Windows):

```powershell
docker compose run --rm `
  -v "${PWD}/seed:/work/seed" `
  -v "${PWD}/playgrounds:/work/playgrounds" `
  -w /work `
  app `
  python seed/seed_prompts.py --email owner@acme.com --password 'your-password'
```

Keep the password out of your shell history by using env vars instead of flags:

```bash
docker compose run --rm -e SEED_EMAIL -e SEED_PASSWORD \
  -v "$(pwd)/seed:/work/seed" -v "$(pwd)/playgrounds:/work/playgrounds" -w /work \
  app python seed/seed_prompts.py
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--email` / `SEED_EMAIL` | — | account email (required) |
| `--password` / `SEED_PASSWORD` | — | account password (required) |
| `--prompts-dir` | `playgrounds/prompts` | directory of `*.txt` prompts |
| `--namespace` | `library` | model-name namespace (`namespace/name`) |
| `--access-level` | `workspace` | `workspace` (all members) or `private` (owner only) |
| `--tags` | `seed` | comma-separated tags on every prompt |
| `--limit` | `0` | import only the first N files (handy for a smoke test) |
| `--dry-run` | off | authenticate and count; write nothing |

**Re-running is safe.** A prompt whose `namespace/name` already exists is skipped,
not duplicated, so you can re-run after adding prompt files.

Smoke test first:

```bash
docker compose run --rm -v "$(pwd)/seed:/work/seed" -v "$(pwd)/playgrounds:/work/playgrounds" \
  -w /work app python seed/seed_prompts.py --email owner@acme.com --password 'your-password' --dry-run
```

## Seeing the data in the UI

The SPA reads the prompt registry from the live backend whenever it runs against
the real API (`VITE_AUTH_MODE=api`, which the dev overlay already sets).
`VITE_DATA_MODE` overrides this independently if you want mock auth but real
prompt data (or vice versa). The baked production image compiles the bundle at
build time, so after a frontend change run `docker compose build caddy && docker
compose up -d caddy` before looking.

On `/app/prompts` the seeded prompts show up in three places, all fed by
`GET /api/v1/prompts`:

- the **workspace stats** — prompt count, and the share of prompts that have
  cleared a human approval. Spend and request volume read `0`: the call ledger is
  a sink with no read path in the MVP, so there is nothing truthful to show.
- the **folder cards** — the registry has no folder table, so one folder is one
  **namespace** of the `namespace/name` model name. Seeding with the default
  `--namespace library` therefore produces a single `Library` folder holding
  everything; pass a different `--namespace` per batch to get several folders.
- the **all-prompts table** below them, and the prompt detail/revision screens.

Other dashboards (evaluation, providers, production metrics, call records) remain
on sample data — those figures come from modules this seed does not populate.

# Module Details

One page per module: what it is made of inside, and what crosses its boundary.

Each page is a standalone interactive HTML diagram — pan, zoom, search, guided views,
light/dark, PNG/SVG export. Open the `.html` in a browser. The `.architecture.json`
beside it is the source; edit that and re-render rather than editing the HTML.

For the system-wide view, see `../1 - Overall Architecture.html` and `../2 - Modules Map.html`.

## The pages

| Module | Kind | What the page shows |
|---|---|---|
| [Access Control](access-control.html) | PLATFORM | Authenticates every actor and answers every *may-this-actor-do-this*. Permission is local — the caller passes the subject in (ADR-0020). Three of the four sanctioned `SECURITY DEFINER` functions live here. |
| [Call Ledger](call-ledger.html) | PLATFORM | The sink. Every completed call, recorded off the response path, priced at write time against an effective-dated table. Every edge on the page points inward. |
| [Chatbot & Orchestrator Agent](chat-orchestrator.html) | FEATURE | One conversational surface that routes a turn to a closed tool catalogue. It proposes writes and never performs them — the write is a `chat.pending_action` row settled by a separate request. |
| [Evaluation](evaluation.html) | FEATURE | The fixed suite, run against the candidate and against the released revision, reporting per-case pass/fail and the cost delta. Release-control pulls the summary; evaluation never calls back. |
| [Gateway](gateway.html) | FEATURE | The OpenAI-compatible surface. Resolves a model name to the released revision, composes, dispatches, falls back. Owns no schema — the only state is a 30 s cache. |
| [Prompt Conversion](prompt-conversion.html) | FEATURE | TXT / Markdown / JSON / YAML into canonical XML. Conversion never saves a revision; the author reviews the XML and saves separately. |
| [Prompt Improvement](prompt-improvement.html) | FEATURE | After release: *is it still doing the job it was approved to do?* Detectors over call metadata plus opt-in re-probing. Adds two things of its own; imports the rest from Prompt Readiness. |
| [Prompt Ingestion](prompt-ingestion.html) | *unspecified* | Bulk import staging: uploaded files become durable staged rows, a worker converts and duplicate-checks them, and only an approved commit proposal writes to the registry. **No lock file — as-built from code.** |
| [Prompt Observation](prompt-observation.html) | FEATURE | The migration audit. Calls the gateway could not resolve, grouped by fingerprint. An open row is work outstanding; an empty inbox is the success condition. |
| [Prompt Readiness](prompt-readiness.html) | FEATURE | Before release: *is this prompt ready for the job it says it does?* A measurement, not an opinion. Owns the probe runner, evidence rail, finding shape and profile reader that Prompt Improvement imports. |
| [Prompt Registry](prompt-registry.html) | FEATURE | Owner, immutable revision chain, and the released pointer — a registry field only Release Control may write. |
| [Prompt Search](prompt-search.html) | FEATURE | Keyword, semantic and duplicate detection. Every read runs behind `visible_subject_filter`, so a missing filter returns zero rows. |
| [Property History](property-history.html) | PLATFORM | The append-only trail. Rows are never deleted at the database privilege level; `actor_id` and `target_id` are values, not foreign keys. Depends on nothing. |
| [Provider Access](provider-access.html) | PLATFORM | The only module that decrypts. Credentials are workspace-supplied, encrypted at rest, never returned by any read API. |
| [Release Control](release-control.html) | FEATURE | The recorded human approval. No auto-release of any kind; only Approved revisions may be released, enforced by a composite foreign key rather than an `if`. |

## How to read a page

- **Boxes are code.** Every internal node cites the file and line it came from — hover the
  `SRC` badge. Archify verifies those citations against the checkout at render time, so a
  wrong path or line fails the build rather than shipping.
- **Colour is a type.** Inbound surface, backend stage, database table, security gate,
  message bus, and everything outside the module in grey.
- **The dashed box is the module boundary**, labelled with the Postgres schema it owns
  (or "owns no schema").
- **Dashed edges are asynchronous, off-path, best-effort, or refusal branches.**
- **The three cards** are Surface (what it exposes), Inside (what it is made of), and
  Guarantees (the constraints and refusal shapes, from the lock file).
- **Guided views** at the top step through the page one reading path at a time.

## Provenance and caveats

Rendered from the working tree at commit `fe39432`. Source links point at
`github.com/ngohuunghia-123/Prope_Prompt_Versioning` at that revision.

Boxes are drawn from **code**; guarantees are drawn from the **lock files**. Where the two
disagreed, the pages draw the code. Those disagreements were collected during this run and
are worth reading alongside the diagrams — several are decisions that were made in code and
never written down, not mistakes.

Two facts span pages and live on only one of them:

- **Two independent import paths exist.** This folder's Prompt Ingestion page draws the
  batch path. ADR-0066's migration scanner (`skills/prope-migrate/register.py`) posts
  straight to the registry's `/api/v1/prompts` and never touches `/api/v1/import-batches`.
- **Prompt Conversion has two in-process callers** that bypass its HTTP surface and its
  `_authorize()` gate — Chat Orchestrator and Prompt Ingestion — both drawn entering
  `convert_source()` directly on the Prompt Conversion page.

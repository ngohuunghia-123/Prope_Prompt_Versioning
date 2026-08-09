# ADR-0048 — Registry search is a trigram index over a trigger-maintained document column

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: prompt-registry — and the answer, for as long as it holds, to *"should we add semantic search"*
**Related**: A-002, A-011, A-013, A-021, A-045, A-050, A-118, A-128, ADR-0002, ADR-0003, ADR-0025,
ADR-0027, ADR-0035, ADR-0038, ADR-0045, BR-01, H-01, OQ-001, OQ-006, OQ-010

## Context

`prompt-registry.lock.yml` puts search in scope as *"Search and filter by title, body, owner, status,
access level, and tag — keyword only, permission-filtered at the query layer"* and budgets it at
**p95 < 500 ms** under *"1,000 prompt properties × 20 revisions, single keyword + two filters"*. It is
the mechanism behind `00_context.md#success`'s *"Time to find the trusted revision of a named prompt —
≤ 30 s in ≥ 80% of attempts"*, and behind the problem statement that started the project: 11 of 11
respondents could not identify the latest revision, 9 of 11 did not know the owner.

Two things were left undecided, and both change the schema.

**Which body.** `body` lives on `revision`, not on `prompt_property`. The scope line reads as a flat
list of prompt-property attributes with `body` among them, but there are twenty revisions per property
in the stated load condition — so "search the body" is a 20× ambiguity sitting on the only number
anyone wrote down. At A-050's 32 KiB cap, twenty thousand revisions is a **640 MB** upper bound on
indexed text; a thousand latest bodies is **32 MB**.

**What a keyword match means.** A-013 is more specific than the lock's restatement of it:
*"Registry search matches **substrings** in title, body, and tags"*. Substring matching and word
matching are different products, and PostgreSQL implements them with different index types. The
distinction is not academic here:

- **OQ-010 is open** — *"What language is the product interface in?"* — and `tsvector` cannot be
  configured without naming a stemming dictionary. Committing to `english` now means a Vietnamese or
  mixed-language body stems to noise, and the fix is a reindex plus a re-audit of every query.
  **UPDATED 2026-08-09: OQ-010 is answered and the answer strengthens this argument rather than
  removing it.** The product ships in Vietnamese (ADR-0053). PostgreSQL bundles no Vietnamese stemming
  dictionary at all, and Vietnamese words are multi-syllable with spaces, so word-based matching is
  weaker here than the English case this bullet worried about — while substring matching is indifferent
  to both facts. What the answer *did* change is the character set in the indexed column: see A-150,
  which folds diacritics and case inside the trigger this ADR already specifies. It does not belong in
  the index expression, because `unaccent()` is STABLE rather than IMMUTABLE.
- **Model names are `namespace/name`** (A-021) and bodies carry `{{variable}}` placeholders (A-011).
  PostgreSQL's default text-search parser classifies slash-separated text as a file-path token, so
  `refund` does not match `support/refund-classifier` under `tsvector`. That is the single most likely
  thing a person types into this search box.

There is also a shape constraint that removes the obvious implementation. The newest revision cannot be
marked with an `is_latest` flag, because ADR-0002 lets no `UPDATE` reach `revision` except `status` —
flipping the previous row's flag is forbidden by a decision the product depends on. The corpus has to
be bounded structurally rather than by a mutable marker.

## Decision

**`prompt_property` carries a `search_text` column, maintained by a database trigger, indexed with
`pg_trgm` GIN, and queried with `ILIKE '%term%'`.**

- **Content**: `title | purpose | tags | the latest revision's body | every revision's change summary`.
  The first four are the searchable surface of the prompt as it stands today. Change summaries are
  included in full across all revisions because A-050 caps them at 200 characters — twenty of them is
  ~4 KiB per property, about 0.6% of what indexing the bodies would cost, and it recovers most of the
  historical recall that indexing every revision was reaching for (*"which prompt did we change for the
  refund thing"*) with human-written text rather than inferred text.
- **Maintained by a trigger, not by the application.** It fires on `INSERT INTO registry.revision` and
  on `UPDATE` of `prompt_property.title | purpose | tags`, and rewrites the column in the same
  transaction. Drift is silent and wrong in the unsafe direction: a body edited without its
  `search_text` rewritten makes the prompt **un-findable by its own new text**, and nothing surfaces
  that — no error, no metric, no failed query, just a prompt that does not come back. This project has
  declined application-maintained invariants five times for exactly that shape (BR-03's constraint,
  ADR-0025's privilege, ADR-0027's schema, ADR-0035's policy, ADR-0045's coverage test). This is the
  sixth.
- **`revision` stays append-only.** The trigger fires on the insert and writes `prompt_property`, which
  was already mutable. ADR-0002 is untouched, and the trigger never writes `revision`.
- **Index**: `CREATE EXTENSION pg_trgm` (a bundled `contrib` extension, trusted since PostgreSQL 13, so
  the migration role creates it without superuser — and the migration fails loudly rather than silently
  if that is not true on the deployed instance), then a GIN index with `gin_trgm_ops` on `search_text`.
  Roughly 2–5× the indexed text: **~100 MB at A-050's cap**, well inside ADR-0033's sizing.
- **Query semantics the user sees**: substring, case-insensitive, matching inside words and inside
  model names. `thentic` finds *"authentication helper"*; `refund` finds `support/refund-classifier`.
  No stemming, so `contract` does not find `contracts`. Terms under three characters cannot form a
  trigram and fall back to a scan of 1,000 rows, which is acceptable rather than hidden.
- **Ordering is `updated_at DESC`, not relevance.** There is no ranking function in the MVP. Because the
  trigger touches `prompt_property` on every revision insert, a freshly edited prompt rises to the top
  of the default list, which is the behaviour H-01 wants.
- **Three filters stack in one statement**: ADR-0035/ADR-0045's row-level security policy supplies the
  workspace boundary invisibly, A-118's `visible_subject_filter` set form supplies the within-workspace
  permission filter in SQL rather than per row, and `search_text ILIKE '%term%'` supplies the keyword.
  They are independent and none substitutes for another.

## Alternatives rejected

Two sub-decisions, each grilled with three candidates.

### On the corpus

**Index every revision's body directly, joining back through a `latest_version_id` pointer.** The
honest competitor: no duplicated text, and the results are still latest-only. Rejected on the bound.
The index covers 20,000 rows instead of 1,000, which is ~150 MB at realistic body sizes but **~2 GB at
A-050's cap** — and A-050 is the only number that actually constrains it, since nothing stops a
workspace from storing 32 KiB prompts. It also puts the index on the append-only table, so every
revision ever written is permanently indexed whether or not anything can still match it.

**Index every revision and return historical hits.** Widest recall, and the only option that answers
*"which prompt used to say X"* directly. Rejected because it surfaces a prompt whose **current** body
does not contain the search term, which is a false positive against the exact task H-01 measures —
*"find the trusted revision"*. A register whose search returns things that are no longer true is a
worse register. The change-summary fold above recovers the useful half of this at 0.6% of the cost.

### On the match semantics

**`tsvector` + GIN with `to_tsquery`.** Smaller index, real relevance ranking, and it scales orders of
magnitude past this pilot. Rejected on three specifics rather than on taste: it requires committing to
a stemming dictionary — and after OQ-010's answer (Vietnamese, ADR-0053) there is no bundled dictionary
to name; it cannot match infixes at all, only prefixes via `:*`; and its default parser tokenises
`support/refund-classifier` as a file path, so the most likely query in this product misses. It is
named below as the first upgrade, using the `simple` dictionary, which needs no language decision.

**Plain `ILIKE '%term%'` with no index.** Seriously considered, and it very likely passes today —
roughly 5–15 ms over 1,000 rows at realistic body sizes, 100–200 ms with every body at the cap, against
a 500 ms budget. Rejected because the index is one migration line and one extension, and the
alternative is discovering the ceiling during a pilot rather than in a migration. It also forfeits
`pg_trgm`'s `similarity()` operators, which are the cheapest available upgrade path.

### On the enrichment question, asked and answered during this pass

**An LLM keyword-extractor / summariser on every save, and/or a vector store.** Raised by the user
during the grill and rejected for the MVP. It is out of scope by declaration —
`00_context.md#scope` lists *"LLM-judge quality scoring; semantic/vector search"* as out, and OQ-001
holds it there — but the architectural reasons are worth recording, because the question will return:

- **It puts a model on the write path of the register.** prompt-registry touches provider-access only
  for a local table read today. Dispatch makes a revision save depend on an upstream provider's
  latency (1–3 s against a `p95 < 300 ms` budget), so it must go through RabbitMQ into `worker` — a
  pending state, a backlog, a retry story, and search results that differ depending on whether a job
  has run.
- **It spends the workspace's own money.** Under BYOK, Prope holds no provider account, so the
  extraction runs on the customer's credential and quota. `00_context.md#constraints`:
  *"Cost must be measured from actual runs; never inferred from prompt token length"* — an extraction
  **is** an actual run. Either it appears in their ledger and they ask why Prope is calling models on
  its own behalf, or it does not and the ledger stops being the truth.
- **It changes the egress story.** Today a body leaves the host only when a consumer asks for a call;
  that is the product. An extractor sends **every** body upstream at save time, including drafts and
  retired prompts nobody intended to run, against a constraints row reading *"nothing leaves that
  host"* and while A-020 still bars real corporate prompts from the pilot.
- **A register indexed by a model's opinion is a weaker register.** Substring search has the property
  that what you find is what is in the text. Extracted keywords are non-deterministic, drift with the
  model version, and fail in both directions — a prompt becomes findable under a word it does not
  contain, or stops being findable after a re-extraction.

The pattern is real and works well — Glean, Notion AI, and enterprise RAG over wikis all do it. Every
corpus it succeeds on is large, heterogeneous, and written by people other than the searcher, years
earlier. Prope's is ~1,000 items, homogeneous, written by the eleven people searching it, with a
**required human-written change summary on every save**. That summary is the enrichment layer, and it
is already in the data — which is why it is now in the index.

## Consequences

- **`search_text` is a second copy of the prompt body, on the table every list endpoint reads.** It must
  never appear in an API response: a `SELECT *` on the list path would return every body in a list
  payload. This is recorded as a security requirement and an owed acceptance criterion, and it extends
  OQ-006's classification question and A-046's never-logged rule to a second column. It is covered by
  the same row-level security policy, because `prompt_property` carries `workspace_id`.
- **The write path gains a trigger and a GIN write.** Revision create — already carrying a history
  append in the same transaction against a `p95 < 300 ms` budget — now also rewrites `search_text` and
  writes the index. GIN's pending-list makes the insert itself cheap and defers the tree merge, so this
  is affordable; it is asserted rather than assumed, in the load plan that already exists.
- **A CI test asserts the trigger exists**, in the same shape as ADR-0025's privilege test and
  ADR-0045's coverage test. A trigger is invisible at the call site — the criticism ADR-0042 levelled at
  absent policies — and the mitigation is the same one this project already uses: make its absence a
  build failure rather than a code-review responsibility.
- **`updated_at` on `prompt_property` now moves when a revision is saved.** Desirable, and new. Default
  list ordering changes accordingly.
- **Historical bodies are not searchable.** *"Which prompt used to mention X"* is answered by opening
  revisions, not by search. Stated cost, not an oversight; the change summaries cover the common case.
- **ADR-0038's process-lifetime cache shape was weighed and rejected here** for the model catalogue, on
  the ground that `POST /providers/{id}/models/refresh` is a real endpoint — under that shape it would
  return 200 and change nothing until a redeploy. prompt-registry therefore caches nothing at all, and
  the gateway's 30 s TTL (ADR-0012) remains the only staleness anywhere in the read path.
- **An ordered upgrade ladder, so the next person to ask finds an answer instead of a vector store:**
  1. `to_tsvector('simple', …)` beside the trigram index. The `simple` dictionary lowercases and does
     not stem, so it needs no language configuration and **OQ-010 stays out of it** — buying
     word-boundary matching, phrase search, and `ts_rank` ordering for one more index.
  2. `pg_trgm`'s `similarity()` / word-similarity operators for typo tolerance and *"did you mean"*.
     Already installed by this decision; no new extension, no new index type.
  3. `pgvector` with embeddings computed in `worker` **on a schedule, never on the save path**, and only
     past A-013's own revisit trigger (*"the 30-second find target fails in usability testing"*).
     A-013 already records that this is additive — *"the same records, a second index"* — and it stays
     additive precisely because it is not being built now.
- **Prior art supports the shape rather than merely permitting it.** A trigger-maintained search column
  with a GIN index is the pattern PostgreSQL's own documentation recommends, and what Django's
  `SearchVectorField` and Rails' `pg_search` implement. Choosing trigrams over word-based search for
  identifier-heavy text is the same conclusion code search reached independently — Google Code Search,
  Sourcegraph's `zoekt`, and Debian's code search all index trigrams, because identifiers, slashes and
  punctuation defeat word tokenisers and people search for fragments. Prompt bodies with `{{variable}}`
  placeholders and `namespace/name` model references are that kind of text.

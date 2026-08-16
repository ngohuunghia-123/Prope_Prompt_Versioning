# `eval/` — retrieval quality for prompt-search

The unit and integration suites assert that search *behaves*: a private prompt
stays hidden, an unindexed one is still reachable, an unreachable provider is a
503 and not an empty list. None of them can fail when search simply stops
finding the right prompt. This directory is the measurement that can.

Built to `docs/materials/7-ai-evaluation-benchmarking.pdf` (golden dataset,
stratified difficulty, adversarial cases, LLM-as-judge, failure analysis) and
`docs/materials/2-rag-pipeline.pdf` (hybrid retrieval, the RAGAS triad, and its
diagnosis table).

## Run it

```bash
# One long-lived database, so re-runs cost nothing but the queries.
docker run -d --name prope-eval-pg -e POSTGRES_PASSWORD=eval -e POSTGRES_DB=prope \
  -p 55432:5432 pgvector/pgvector:0.8.6-pg17

PROPE_EVAL_DATABASE_URL="postgresql+asyncpg://postgres:eval@localhost:55432/prope" \
  python -m eval.retrieval.run_eval --limit 200 --label mychange
```

Leave `PROPE_EVAL_DATABASE_URL` unset and the harness starts a throwaway
container instead. `.env` is read automatically for the provider keys.

| Flag | Meaning |
|---|---|
| `--limit` | corpus size. Below ~110 not every golden target is present; the run says so. |
| `--system` | `ai`, `quick`, or `both` (default) |
| `--k` | results requested per query (default 10) |
| `--no-index` | corpus is already indexed — skips extraction and embedding entirely |
| `--judge` | grade the top 3 of every query with the App Agent, rubric 1-5 |
| `--label` | names the file written to `eval/result/` |

## What it measures

| Metric | Reads as | Points at |
|---|---|---|
| `hit_at_1` | the first row was right | what most people actually see |
| `context_recall_at_3` / `_at_10` | the wanted prompts came back | **retrieval**: representation, chunking, query handling |
| `context_precision_at_3` | the top 3 was relevant | **ranking**: right prompt present but buried |
| `mrr`, `ndcg_at_10` | how near the top, graded | ordering |
| `abstention_rate` | out-of-scope queries returned nothing | the import dialog crying wolf |
| `latency_ms` | p50 / p95 | the lock's p95 < 1,000 ms budget |

Relevance is graded, not binary: `primary` is what the person wanted, `secondary`
is a neighbour they would accept. A corpus of 375 documents in one genre has real
near-answers, and scoring them as misses makes every number noise.

## The golden set

`retrieval/golden.py` — 36 hand-written queries plus 6 duplicate probes
generated from the corpus, stratified per the deck's template: easy lookups,
paraphrases with no shared vocabulary, hard cluster-discrimination, Vietnamese
queries against an English corpus (ADR-0053 makes Vietnamese the interface
language), and adversarial out-of-scope questions whose correct answer is an
empty list.

Labels are **file stems** from `playgrounds/prompts/`, so any reviewer can check
one by opening the file. They were written by reading the target prompts, which
is the step the deck (p20) says decides whether the whole evaluation means
anything.

## The corpus

A deterministic slice of `playgrounds/prompts/`, converted by the real
`seed/converter.py` and inserted through the real `create_prompt` /
`create_revision` commands — including the seed script's boilerplate purpose
(`"Imported prompt library entry (x.txt)."`), because that is what a seeded
workspace actually contains.

Alphabetical fill after the golden targets is deliberate: it pulls in the whole
`agent_*` block, the densest cluster of near-identical documents in the library
and therefore the hardest distractor set available.

## Cost

Indexing is the expensive half — one LLM extraction and one embedding per
prompt. `eval/cache/artifacts.jsonl` (git-ignored) caches both, keyed
separately: changing how the embedded document is assembled re-embeds without
re-extracting. A first run over 200 prompts takes about three minutes; every run
after that is seconds plus the queries.

## Reading a result file

`eval/result/<timestamp>-<label>.json` holds the config, the per-system summary,
every query's retrieved list with scores and `matched_fields`, the five worst
queries with what they returned instead, and — with `--judge` — the judge's
scores and every place it disagrees with the labels. That last section is a
check on the golden set, not on the ranker: an unlabelled result the judge calls
exact is a hole in the labels that silently depresses precision for every run
compared against it.

## Traces

With `LANGFUSE_*` configured, each query emits a span carrying `query_id`,
difficulty, the retrieved stems and its scores, alongside the extraction spans
the indexing path already emits (quality, groundedness, tokens, cost, failures).

**Query text is never sent**, and neither is any prompt content. Six of these
queries are 1,800-character extracts of real prompt files — that is what a
duplicate probe is — and A-020 does not exempt an evaluation harness from a rule
a product feature would be held to. `query_id` identifies the row in
`golden.py`, which is in git.

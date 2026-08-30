# 05 — Evaluation: the cached answer is the gated answer

The cache is not a second evaluation path. It stores the **output of the existing gate** and
re-runs that gate on every read, so a cached suggestion is indistinguishable from a fresh one
by construction.

## Decisions

| # | Decision | Value |
|---|---|---|
| D1 | The gate is the only judge | `_gated` (the suggester's id-coercion, dedupe, cap and confidence clamp) is a pure function of the model's prediction. The cache stores the **raw prediction fields** and runs `_gated` on read — a hit goes through the exact same drop/cap logic as a miss. There is no second, looser path for cached rows |
| D2 | What is stored is what a person would have seen | The stored `findings` JSON is the gated `DatasetSuggestion` list (`dataset_id`, `name`, `reason`, `confidence`), bounded by `SUGGESTION_CAP`. An empty gated list (a valid "nothing truly applies" answer) is stored as an empty array and served as such |
| D3 | No judges anywhere | The existing design has no LLM-as-judge on the suggestion path, and the cache adds none. A hit is not re-scored; it is re-gated (a pure function) |
| D4 | Gate-bug invalidation | Because the gate re-runs on read, a gate bug fix needs **no** cache invalidation: the stored raw prediction flows through the corrected gate on the next hit, and a row that now fails is dropped (`miss_stale`). This is the property that makes the cache safe to ship before the gate is frozen |
| D5 | Quality signal | The disposition funnel is unchanged (suggest → gated → person ticks). The cache adds one quality metric: `llm_cache_total{feature="suggest_datasets", result="hit"}` — a rising hit rate is the expected steady state for a stable catalogue; a *falling* hit rate is the first sign of a catalogue or model churn worth looking at |
| D6 | The eval-case drafter is a follow-up | `draft_cases` is equally cacheable (its inputs are `prompt_body`, `prompt_title`, `brief`, `case_target`) but its output is a *draft a person edits*, so a stale cached draft would be more costly than a stale suggestion. It is explicitly a follow-up (shape D13), wired through the same seam once the suggester proves out |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Cached row bypasses the gate | `_gated` re-runs on read (D1) |
| Gate fix requires cache purge | no purge needed — re-gate on read (D4) |
| Empty valid answer not cacheable | empty array stored and served (D2) |
| Cached draft edited by a person is stale | drafter excluded from v1 (D6) |
| Silent catalogue churn | hit-rate metric + catalogue-version key (D5 + 02-D8) |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| E1 | blocker | Stored rows pass through `_gated` on read | D1 + test |
| E2 | blocker | Empty gated list stored as empty array | D2 + test |
| E3 | high | No LLM-as-judge introduced | D3 |
| E4 | med | Gate-fix needs no invalidation (documented property) | D4 + test |
| E5 | med | Drafter excluded from v1 with the reason written | D6 |

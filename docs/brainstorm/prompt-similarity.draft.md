---
id: prompt-similarity
status: partially-implemented
owner: user
created: 2026-08-20
affects:
  - docs/modules/prompt-search.lock.yml — the duplicate check behind POST /prompts/search/similar
  - docs/modules/evaluation.lock.yml — gate.score_body_against_suite as the issue-3 signal
  - src/prope-fe/features/prompt-lifecycle — the import flow and SimilarPromptsDialog
supersedes: nothing yet — promote to an ADR when the open questions below close
---

# Prompt similarity — what "the same job" means, and how it is decided

**Why this exists.** The import screen's duplicate check returns three prompts that share
nothing with what was pasted. It is not a tuning problem. The pipeline computes *which
vectors are nearest* and the dialog renders that as *these are duplicates*, and nothing in
the code has ever said what "duplicate" means.

The measurement was already there and read as a pass:
`eval/result/*-smallcorpus-guards.json`, category `duplicate-probe` — `mrr 1.0`,
`context_precision_at_3 0.333`, `mean_results 10.0`. The right prompt is at rank 1 every
time and two of the three rows shown are noise.

---

## 0. What is built, and where

The free half of the funnel and the adjudicator ship; the two paid stages do
not. That split is not a convenience — it is §1.5's error economics applied to
the schedule. What is built can be wrong in the recoverable direction (a missed
duplicate, an offered revision); what is not built is the evidence that would be
needed to recommend the unrecoverable one.

| Design | Code | Status |
|---|---|---|
| §1.2 the five verdicts | `prompt_search/comparison/domain.py` | built |
| §1.3 compare blocks, not documents | `canonical_prompt.blocks_of`, `comparison/structural.py` | built |
| §2.0 retrieval, recall-tuned at K=20 | `RETRIEVAL_LIMIT`, `api.search_similar_prompts` | built |
| §2.0 free structural pre-filter 20 → 5 | `comparison/structural.rank_candidates` | built |
| §2.0 one adjudication call, no reranker | `agent/comparison.adjudicate` | built |
| §2.0 index coverage as the recall ceiling | `repository.count_indexed`, `similar.coverage.partially_indexed` | built |
| §2.1 differential behavioural testing | — | **not built** |
| §2.2 stage 2a, the input contract | `comparison/input_contract.py` | built |
| §2.2 stage 2b, the declared output contract | `comparison/output_contract.py`, migration 0035, `pipeline.describe` | built; extracts on demand and caches back |
| §2.2 stage 2c, observed output vs A's assertions | — | **not built** (rides on §2.1) |
| §2.3 cost, latency and quality deltas | — | **not built** |
| §3 structured hand-off, never a summary | `Finding` code + params, no prose on the wire | built |
| §4 an evidence sheet, not a verdict | `EvidenceSheet`, `verdict.recommend` | built |
| §3 the divergence shown verbatim | `CandidateOverlap` — per-block containment + the shared terms | built |
| §6 the dialog default | `SimilarPromptsDialog`, `usePromptImportFlow` | built |
| the display floor, over `related` rows only | `verdict.MATCH_FLOOR` (0.25), `verdict._survives_floor` | built, **calibrated — see §7** |
| the funnel narrating itself | `comparison/trace.py`, SSE on the same route, `SimilarityTraceSheet` | built |
| §7 the labelled pair set | `eval/retrieval/similarity.py`, `tests/golden/` | **built — the blocker is cleared** |
| ranking discounted for candidate bulk | `structural.FOCUS_EXPONENT`, `_focus` | built, **new — see §7** |

**The `Action.USE_EXISTING` gate is how the missing half is enforced rather than
merely noted.** `verdict.USE_EXISTING_REQUIRES_MEASUREMENT` is `True`, and while
it is, a `same` verdict recommends *add as a revision* and nothing recommends
discarding the incoming prompt. Building §2.1 and §2.3 is what earns the right to
flip it — and flipping it without them would be the one error in §1.5's table
with no recovery.

**The screen shows its working, and that is a §3 commitment rather than a
nicety.** A verdict on its own is an assertion a reader can only accept: it
invites agreement or nothing. So each candidate carries `overlap` — which
canonical blocks overlapped, the containment per block, the shared words that
produced it ranked by IDF weight, the `{{variables}}` both prompts read, which
retrieval legs fired — plus the adjudicator's closed-vocabulary reason codes, and
the two bodies aligned block against block rather than document against document.
Blocks are ordered by how much the ranking weights them, so `instructions`
precedes `system` even when persona scored higher, which between two prompts from
one library it usually does; ordering that agreement first would reproduce the
whole-document embedding's mistake in the interface. **The point is falsifiability
by a human**: three unrelated prompts were shown as duplicates for months
precisely because nothing on that screen could be contradicted.

> **Superseded by §7's measurements.** The three paragraphs below described the
> floor as first shipped — 0.90, applied to every row. The labelled set showed
> that 10 of 10 confirmed duplicates fall under it and that the twin and decoy
> ranges overlap, so it now governs `related` rows only, at 0.25. The reasoning
> about *where* it sits in the funnel still holds and is why it was cheap to
> change; the number and the population it applies to did not survive contact
> with evidence. Kept as written, because the cost it names is exactly the one
> that was later measured.

**A 90% display floor now sits at the end of the funnel, and it is a deviation
from §2.0 rather than an implementation of it.** Everything upstream of it
deliberately refuses to threshold — retrieval owes recall, the pre-filter orders
and rejects nothing, "a candidate that never enters can never be confirmed *or*
rejected" — and the floor does not touch any of that. It applies to a candidate
that has already been retrieved, ranked, judged and contract-checked, and it
answers a different question: not *is this worth checking* but *is this worth
putting in front of a person*. It runs before `recommend`, because a prompt the
screen does not list must not be the prompt the screen pre-selects.

The number it thresholds is `match_score`: the weighted containment divided by
what was attainable for that incoming body, so an identical prompt scores 1.0 and
"90%" is a claim about coverage a reader can check. `structural_score` is the
same evidence unnormalised and is diagnostic only — its ceiling moves with the
incoming prompt, so a floor on it would mean five different things for five
different prompts.

**What the floor costs, recorded here because it is a real cost and not a
rounding.** A genuine duplicate that was rewritten rather than copied — same job,
same contract, different words — scores well below 90% and is now hidden, *after*
the adjudicator has already said `same`. That is the funnel finding a duplicate
and the display discarding it. `below_floor` counts them, the dialog and the
trace both say so, and `PROMPT_SEARCH_MATCH_FLOOR` moves it without a deploy —
but the honest reading is that the screen is now a **near-copy check**, and the
`related` and `variant` context rows mostly disappear with it. §7's labelled pair
set is what would settle whether 0.90 is the right number; until it exists this
is a chosen default, not a measured one.

**The funnel narrates itself while it runs.** The check has been measured at up
to twenty-five seconds and used to spend all of them behind a spinner — which is
the §3 legibility problem one level up, and it got worse with the floor, because
*nothing found* is now the ordinary outcome and a check that runs for twenty
seconds and then vanishes has told nobody anything. So each rung emits an event
as it completes (`comparison/trace.py`: a closed step vocabulary, machine counts,
no prompt text) and the import screen renders them in a bottom sheet as they
arrive. `Accept: text/event-stream` on the existing route rather than a second
path: one resource, two representations, the same declared action, and a final
`result` frame carrying the payload the JSON caller would have received.

The shared terms are the one content-bearing field in the comparison payload.
They are admissible on the import dialog's response, which already carries two
thousand characters of the candidate's body as `body_preview`, and nowhere else —
never a log field, never a metric label, never a `Finding.param`.

**What the ranking is still allowed to be bad at.** Block *vectors* — the
representation lever in §2.0 — are not built either: retrieval still embeds the
enriched whole document and the block-level view begins at the free pre-filter.
That is deliberate sequencing rather than an omission: the pre-filter proves the
signal on the corpus for free, and `recall@20` measured against a labelled set is
what would justify re-embedding it. OQ-c (the vector floor) stays open for the
same reason — it cannot be calibrated before the representation is settled.

## 1. What was decided

### 1.1 Similarity is a property of substitution, not of text

Two prompts do the same job when **swapping one for the other would not break the caller.**
Not "the text is alike" — a prompt is a program, and a prompt library is one genre, so
textual likeness is dominated by the genre and says almost nothing about the job.

**This relation is asymmetric.** "B can serve A's callers" and "A can serve B's callers"
are different claims, and a cosine is symmetric by construction, so the current pipeline
cannot represent the difference at all.

### 1.2 The verdict set is richer than same / related / unrelated

| Verdict | Meaning | Action |
|---|---|---|
| `same` | substitutable both directions | compare quality → revision, or use the existing one |
| `supersedes` | B does A's job and more | neither a revision nor a redirect is correct |
| `variant` | same task, incompatible contract — output format, variables, language | new prompt, say why |
| `related` | same domain, different task | new prompt, shown as context |
| `unrelated` | — | not shown at all |

`variant` and `supersedes` are the cases a naive judge calls `same`, and both are cases
where "use the existing prompt instead" is actively wrong. They are a likely share of the
false positives being reported.

### 1.3 Compare canonical blocks, not documents

Every revision body is canonical XML with six flat blocks (`canonical_prompt.py`):
`system`, `context`, `instructions`, `output_format`, `examples`, `constraints`.

This is not a prose-comparison problem. It is a comparison of two structured records with
the same six fields.

| Block | Carries |
|---|---|
| `instructions` | the task — the job itself |
| `output_format` | the output contract — short, highly discriminating, currently drowned |
| `context` | domain assumptions |
| `constraints` | the policy envelope |
| `system` | persona — weak signal, high volume |
| `examples` | near-noise for this purpose, high volume |

The pipeline embeds the whole document, so `system` + `examples` + `constraints` — the
longest and most genre-generic blocks — dominate the vector while `instructions` contributes
a few percent. That is the false positives, mechanically explained.

### 1.4 Three levels of evidence, cheapest first

**Level 1 — hard, deterministic, free.** `prompt_composition.required_variables()` extracts
the `{{variable}}` set exactly; the `output_format` block is its own field. These cannot
establish sameness but they **refute** it with certainty: disjoint variable sets means a
caller cannot swap them, before a single token is spent.

**Level 2 — judged, per block.** An LLM reading `instructions` + `system` for task, `context`
for domain, `constraints` for policy. Short inputs, localizable failures. Limit: it judges
what a prompt *says* it does.

**Level 3 — behavioural.** What the prompts actually do. Authoritative, expensive, and
**asymmetric — passing A's suite proves B is _at least_ A, never that B is _only_ A.** A
superset passes every one of A's cases. This is why level 2 survives even when level 3 runs.

### 1.5 The error economics — "use the existing one instead" is the dangerous recommendation

| Error | Cost | Recoverable |
|---|---|---|
| Miss a real duplicate | a duplicate in the registry | yes — search finds it; the 0.9 index-time check flags it |
| Wrongly offer "add as revision" | an immutable revision on the wrong prompt (A-021) | expensively — a second revision, permanent history |
| **Wrongly say "use X instead"** | **the person discards their prompt and adopts one that does not do their job** | **no — it fails silently, in production, months later, traceable to nothing** |

So the evidence bar inverts from intuition: **"use X instead" requires more evidence than
"add as revision," never less.** It requires a `same` verdict *and* a measured comparison.
It is never a default and never an unmeasured guess. The unmeasured default is **create
new** — the outcome that discards nothing and writes something recoverable.

---

## 2. The three sub-flows

From the user's decomposition. Five metrics, three issues, and the cost order falls out of it.

| # | Metric | Issue it answers |
|---|---|---|
| 1 | Are both prompts doing the same task? | does swapping change the output |
| 2 | Same audience / same subject? | does swapping change the output |
| 3 | Do they require the same inputs? | does swapping break the running flow |
| 4 | Is the output structure the same? | does swapping break the running flow |
| 5 | Is the new one cheaper or better? | does swapping raise cost or lower quality |

**Run them in cost order, not diagram order.** Metrics 3 and 4 are free — `required_variables()`
and the `output_format` block. They gate everything downstream: a pair with disjoint variable
sets never reaches a paid dispatch.

### 2.0 Candidate retrieval — the mouth of the funnel

Every flow below operates on a **pair**. Nothing produces the pair. This is the prerequisite,
and it is the original issue: *"Làm sao xác định được prompt cần kiểm tra trong số 1000 prompt?"*

**At 1000 this is not a speed problem.** pgvector over 1000 rows is milliseconds and the lock
file's p95 budget already assumes that corpus. No ANN, no sharding, no clustering. It is a
**ranking** problem: get the true match into a top-K small enough to pay for.

**The tuning inverts from §1.5, and the inversion is the point.** When the probe's top three went
straight to a human, every row was an accusation and precision ruled. With an adjudicator behind
it, retrieval's only duty is **not to miss** — a candidate that never enters can never be
confirmed *or* rejected. So: cap K, do not threshold hard, and let the later stages reject.
Precision moved downstream; recall is what the mouth of the funnel owes.

```
1000 prompts
   │  retrieval — vector + lexical, recall-tuned, ~milliseconds
   ▼
 ~20 candidates
   │  structural pre-filter — cached descriptors, block signals
   │  free: no dispatch, no LLM call when descriptors are already extracted
   ▼
  ~5 candidates
   │  adjudicator — ONE call over all five
   ▼
 0–2  same / supersedes
   │  behavioural — issues 1, 2c, 3
   ▼
 the evidence sheet
```

Each rung costs roughly 10× more per item and carries 5–10× fewer items. **The total bill is
bounded by the last rung running on at most two candidates** — that is what makes the design
affordable at 1000.

**The lever is representation, not machinery.** Store a vector **per discriminating block** and
rank primarily on `instructions` — the block that carries the job — instead of one
whole-document vector where `system` + `examples` + `constraints` drown it (§1.3). Symmetric on
both sides. No new model, no new service: a different column layout on the index row, dropped
into `ranking.fuse`, which already has a pluggable ranker and a harness that can prove it helped.

**Filters that look free and are wrong.** At retrieval, almost nothing may exclude:

- **Variable set** — a true duplicate can rename its variables. Filtering drops exactly the pair
  being looked for. *Signal, not gate.*
- **Folder / namespace** — cross-folder duplicates are the fragmentation this exists to catch.
  *Boost, not gate.*
- **Language, output modality** — these define `variant`, which is still shown. *Signal, not gate.*

**The only legitimate hard filter is visibility**, which already exists. Everything else ranks.

**Index coverage is the recall ceiling, and nothing reports it.** Indexing is async and
soft-failing by design; a prompt never indexed, or stale, cannot be retrieved at all. At 1000
prompts the unindexed-plus-stale share *is* the ceiling, so *% indexed / % stale / oldest
unindexed* is a prerequisite metric, not a dashboard nicety. Otherwise ranking gets tuned
against a corpus that is quietly part-invisible.

**Target: `recall@20 ≈ 1.0`** on the labelled set. If the true duplicate is in the top twenty
the funnel finds it — a far softer target than the `precision@3 ≥ 0.9` that applied when the
probe fed a human directly, and measurable with the same golden set.

#### No reranker model

**The adjudicator already is the cross-encoder.** It scores ≤5 candidates jointly against the
four axes, and it is strictly more capable than a relevance reranker, because the question is
not relevance — it is *same job across task, inputs, output contract, domain*.

**A reranker cannot fix recall.** It only reorders what retrieval returned. If the true duplicate
is not in the top 20, no reranker recovers it — so weak retrieval is a representation problem and
the fix is block vectors. Worth stating because *"add a reranker"* is the reflexive answer to bad
retrieval and it treats the wrong layer.

**The price would be real.** `ML stack: n/a — Prope trains and serves no models` is a stated
property. A cross-encoder means either a new inference service — against ADR-0033's seven
services and A-012's *debuggable by one person* — or a third-party rerank API, a new external
dependency with its own credential-ownership question. Either is an ADR reversal for a marginal
gain on a 20 → 5 step.

**Decision rule, measurable before committing:** run `recall@K` once block vectors exist.
`recall@20 ≈ 1.0` → no reranker; the free structural rerank sorts 20 into 5. Needing `K = 100`
→ reconsider, because a hundred is too many for cheap signals to sort and too many for one
adjudicator call. If a reranker ever earns its place it will be for **the AI search box**, which
has no adjudicator behind it and feels ranking quality directly.

### 2.1 Issue 1 — behavioural equivalence by differential testing

```
mimic-generator agent  ->  run identical inputs on both versions  ->  per-pair comparator
```

**The generator emits inputs only. No expected outputs.** An expected output written by
reading prompt A is what A *claims* it does — a declarative judgment wearing behavioural
clothes, carrying the same blind spot. Compare A's actual output against B's actual output;
no ground truth needed, no agent opinion about what is correct, one less generation step.

**Inputs are stratified for coverage, not for realism.** Realistic "normal user" traffic
samples exactly where two prompts agree. Four categories:

- best case / normal path
- ambiguous input
- out-of-scope input
- **constraint-probing input** — on topic but forbidden. Out-of-scope is off-topic and both
  prompts decline it. A constraint probe is the medical question put to an assistant whose
  `constraints` block says never give medical advice. That is where a dropped rule shows up,
  and it is the divergence release control exists to catch.

**A noise floor is mandatory.** Same prompt, same input, run twice, and the outputs already
differ. Without a control there is no way to separate "B behaves differently" from "the model
is stochastic." So A is run against itself and that pair is scored too: the threshold is
**"at least as close as A is to itself,"** not a fixed number.

**Judged one pair at a time.** Per-pair metrics: task alignment, key information,
conclusion/decision. Following `eval/retrieval/judge.py` — each pair judged alone, no list to
be first in. A comparator that sees every pair at once lets strong best-case results wash out
the one edge case that mattered.

**"Behavioral consistency" is not a comparator metric.** It is a property of the whole set and
belongs to aggregation code, not to the agent. *(Removed on the user's call.)*

**Aggregation is a veto rule in code, not a mean and not an agent's impression.** Best case
5, 5, 5 and out-of-scope 1 averages to "very similar" — and that 1 is the finding. Any edge
case below threshold disqualifies `same`, regardless of the happy path.

**Extension, cheap and unlocking:** generate a second input set from **B**. Cases from A test
"can B serve A's callers"; cases from B test the reverse. The gap between the two answers is
what separates `same` from `supersedes`.

### 2.2 Issue 2 — compatibility, in three stages

**Not one problem.** Metric 3 is exact and free; metric 4 is neither. Treating them as one
"free mechanical check" was wrong and is corrected here.

```
                 ISSUE 2 · "thay prompt mới vào có làm hỏng luồng đang chạy không?"


  A = released (has callers)            ┌────────────────────────────────────┐
  B = candidate                         │  issue 1's differential run        │
       │                                │  B's actual outputs over N inputs  │
       │                                └─────────────────┬──────────────────┘
       ▼                                                  │ free ride
┌──────────────────────────────────┐                      │ 0 extra dispatch
│ 2a   INPUT CONTRACT              │                      │
│      required_variables(A) vs B  │  free · exact        │
│      no model · no dispatch      │  runs FIRST          │
└────────────────┬─────────────────┘                      │
                 │                                        │
      ┌──────────┴───────────┐                            │
      │                      │                            │
   B ⊃ A                  B == A                          │
   or rename              or B ⊂ A                        │
      │                      │                            │
      ▼                      ▼                            │
 ■ HARD VETO      ┌──────────────────────────────────┐    │
   stop here      │ 2b   DECLARED OUTPUT             │    │
   nothing spent  │      <output_format> → descriptor│    │
                  │      {modality, keys, lang, len} │    │
                  │      1 LLM call · cached/revision│    │
                  └────────────────┬─────────────────┘    │
                                   │  PREDICTION          │
                                   ▼                      │
                  ┌──────────────────────────────────┐◀───┘
                  │ 2c   OBSERVED OUTPUT             │
                  │      B's outputs checked against │
                  │      A's STRUCTURAL assertions   │
                  │      json_schema · regex         │
                  │      max_length · required_phrase│
                  │      asset_count · asset_type    │
                  └────────────────┬─────────────────┘
                                   │  CONFIRMATION
                                   ▼
                  ┌──────────────────────────────────┐
                  │     COMPATIBILITY FINDINGS       │
                  └───────┬──────────────────┬───────┘
                          │                  │
                          ▼                  ▼
                     ■ HARD                ○ SOFT
                     new required var      modality changed
                     json_schema violated  longer than max_length
                     │                     language changed
                     │                     │
                     ▼                     ▼
                 final agent           final agent
                 CANNOT trade away     MAY weigh against
                                       cost / quality gain
```

#### 2a — input contract. Free, exact, runs before anything is spent

`prompt_composition.render()` raises `MissingVariable` for any placeholder without a value and
**ignores extras** — it iterates `required_variables(body)` and nothing else. So compatibility
is set math with a direction:

| relation | verdict |
|---|---|
| `required(B) == required(A)` | compatible |
| `required(B) ⊂ required(A)` | **compatible** — callers still send the extras, B ignores them |
| `required(B) ⊃ required(A)` | **breaking** — every caller gets `MissingVariable` |
| partial overlap, or a rename | **breaking** — the new names are never supplied |

Fewer variables is safe; more is fatal. No model, no dispatch, no threshold, no calibration.

**This answers breakage, not sameness.** `{{document}}` renamed to `{{text}}` is mechanically
breaking and semantically the same job. 2a feeds the veto list and contributes nothing to the
`same job?` verdict — the two questions stay separate.

#### 2b — declared output contract. One cached call, positioned as a gate

The output contract lives in `<output_format>` as prose. Comparing two prose blocks by
embedding is §1.3's mistake one level down. Instead: **extract a normalized descriptor from
each block independently, then compare the descriptors in code.**

Worked example:

```
A.<output_format>                          →  descriptor A
"Trả về JSON, chỉ JSON, không có văn bản       modality:    json
 nào khác. Các khoá: decision (approve |       keys:        [decision, reason, confidence]
 reject | escalate), reason, confidence."      enums:       {decision: [approve,reject,escalate]}
                                               bare:        true          ← "chỉ JSON"
                                               language:    unspecified
                                               cardinality: single
                                               length:      unspecified

B.<output_format>                          →  descriptor B
"Trả lời bằng JSON gồm decision và reason.      modality:    json
 decision là approve hoặc reject."             keys:        [decision, reason]
                                               enums:       {decision: [approve,reject]}
                                               bare:        unspecified   ← never says "only"
                                               ...

compare in code:
  modality   json == json                          ok
  keys       B ⊇ A ?   confidence missing          ■ HARD
  enums      B ⊇ A ?   escalate dropped            ■ HARD
  bare       A true, B unspecified                 ■ HARD  (B may wrap in ``` fences)
```

Three quotable findings instead of "these look fairly similar."

**The direction rule is the MIRROR of 2a's, and reversing it would be a silent bug.** For
*inputs*, B must require a **subset** of A. For *output keys and enum values*, B must produce a
**superset** of A — a consumer reads the keys it expects and ignores extras; drop one and it
throws. Write it as a named function, not an inline comparison.

**Descriptor fields — only what a machine consumer trips on:** `modality`, `keys`, `enums`,
`bare` (does it forbid preamble and code fences — the most common real-world break, and it
gets its own field), `cardinality` (single vs list), `language`, `length`. Tone, ordering,
verbosity and style are **not** in it: they change the output without breaking the flow, which
makes them issue 1's business.

**The extractor must be able to answer `unspecified`.** That is what feeds the
undeclared-means-breaking rule, exactly as `UsageProfile` carries `undeclared` as a real value
on every axis. An extractor that always fills in a plausible value quietly destroys the rule.

**Extract per revision, never per pair.** The descriptor is a property of one revision. Cached
by `version_id`, and A's is almost certainly already computed — so a comparison costs **one
call for the incoming body**, not one per candidate. Extracting per pair would also bias the
result: an extractor that sees both blocks at once is drawn toward finding them alike, the same
anchoring problem as judging N pairs holistically.

**Why 2b exists at all, given 2c arrives free:** it is a cheap prediction that can cancel an
expensive confirmation. If A returns bare JSON and B returns markdown prose, that is known
before issue 1 spends 2N dispatches discovering it. **2b's value is its position in the
pipeline, not its findings.**

Mechanically it is `MetadataExtraction`'s shape (`prompt_search/agent/dspy_program.py`): typed
DSPy signature owning the output shape, Langfuse-managed instruction, temperature 0, and the
untrusted-input boundary — the block is somebody else's prompt text. No new machinery.

#### 2c — observed output contract. Free, and authoritative

A's eval suite already holds a machine-readable output contract: the **structural** assertion
types — `json_schema`, `regex`, `required_phrase`, `max_length`, `asset_count`, `asset_type`.
Somebody wrote those down as *the output must look like this*.

Issue 1 has already dispatched B over N stratified inputs. Run A's structural assertions
against those same outputs: **zero extra dispatches.** Issue 2's authoritative half rides free
on issue 1's spend.

#### The rules that hold across all three

- **`B ⊂ A` is compatible.** `render()` only raises on what is missing.
- **A rename is breaking even when the job is identical.** Mechanical, not semantic.
- **Undeclared → assume breaking.** No suite plus a vague `<output_format>` establishes no
  contract, and *not established* is never *compatible*. Same posture as
  `score_body_against_suite` returning `None` rather than an empty pass.
- **2b and 2c disagree → trust 2c, and record the disagreement.** It means the
  `<output_format>` block is lying about what the prompt does, which is its own finding.

#### Output shape

Not a score. A findings list, split:

- **hard** — new required variable; a structural assertion of A's that B's output violates.
  A veto the final agent cannot trade away (§4).
- **soft** — modality changed, output longer than A's `max_length`, language changed. The human
  weighs these against a cost or quality gain.

**2a is pure and free enough to run on every save**, not only at import — which is exactly what
`prompt_readiness/rules.py` Lane A already does on a debounced keystroke. *"This revision adds a
required variable; existing callers will break"* is worth surfacing on its own, independent of
the duplicate check.

### 2.3 Issue 3 — cost, latency and quality

```
        ISSUE 3 · "thay prompt mới vào có làm tăng chi phí vận hành
                   hoặc giảm chất lượng đầu ra không?"

  A = released                                   B = candidate
       │                                              │
       │                                              ▼
       │                        ┌─────────────────────────────────────┐
       │                        │ gate.score_body_against_suite       │
       │                        │ dispatch B over A's OWN suite       │
       │                        │ spends · ceiling checked first      │
       │                        │ writes NO rows                      │
       │                        └──────────────────┬──────────────────┘
       ▼                                           │ per case: outcome,
┌──────────────────────────────┐                   │ tokens, latency,
│ A's stored run               │                   │ output_content
│ CaseResultRow, per case:     │                   │
│   outcome                    │───── matched by case_id ─────────────┐
│   input/output_tokens        │                   │                  │
│   latency_ms                 │                   │                  │
│   output_content  ← STORED   │                   │                  │
└──────────────┬───────────────┘                   │                  │
               │                                   │                  │
               └───── binding check ───────────────┘                  │
                      A.upstream_model vs B.upstream_model            │
                      differ → ⚑ ATTRIBUTION WARNING                  │
                                                                      ▼
        ┌──────────────────┬──────────────────────┬─────────────────────────┐
        │ CONFORMANCE      │ COST + LATENCY       │ QUALITY DELTA           │
        │ regressed        │ per-case matched     │ pairwise preference     │
        │ strict           │ token delta: solid   │ B vs A on stored output │
        │ deterministic    │ latency: advisory    │ position randomised     │
        │ from the suite   │ NO extra dispatch    │ NO extra dispatch       │
        └────────┬─────────┴──────────┬───────────┴────────────┬────────────┘
                 │                    │                        │
                 ▼                    ▼                        ▼
            ■ HARD               ○ SOFT                  ○ SOFT
            a case that          cost / latency          + the output pairs
            passed no            delta, with its         shown side by side
            longer does          basis stated            to the reviewer
```

#### What the current baseline does, and what it does not

- `latest_completed_run(version_id, suite_id)` — the most recent COMPLETED run for that version
  and suite, with **no age filter**. A baseline from three months ago is used exactly like one
  from this morning.
- The baseline is **stored case outcomes**. `gate.py` builds `before = {case_id: outcome}` and
  the only thing reaching `CaseVerdict.baseline` is the string `PASS` / `FAIL` / `ERROR`.
- `regressed` is strict and correct: candidate not PASS while baseline was PASS *or absent*. A
  case that was already failing and still fails is not a regression. **Keep that strictness** —
  it is the whole answer to "cheaper but worse": a saving does not launder a broken case.
- **`GateResult` carries no cost and no latency field.** The candidate's usage goes to
  `price_probe_usage`, gets billed, and is discarded. Nothing is compared. Issue 3 needs those
  fields surfaced; the data already exists per attempt.
- The binding **is** recoverable — a run carries `version_id`, a revision is immutable (A-021),
  so `run → version_id → revision.upstream_model` is exact. No column is needed.

#### Attribution — the check that is missing

`score_body_against_suite` never compares the two bindings. The candidate carries its own
`provider_config_id` / `upstream_model` through `CandidateRevision`; the baseline run used the
released revision's. When they differ — exactly what happens when the new prompt proposes a
different model — the gate reports `regressed` without noting that the model also changed, and
the reviewer cannot tell which one did it.

**Decision: flag when candidate binding ≠ baseline binding**, and either hold the model constant
for the comparison or label the result as measuring both changes at once.

The deeper problem survives that fix: `gpt-4o` in May and `gpt-4o` in August are not the same
model. Recording the string cannot catch provider-side snapshot drift; only re-running A
concurrently can (see OQ-h).

#### Cost and latency

`CaseResultRow` stores `input_tokens`, `output_tokens` and `latency_ms` **per case**. So the
comparison is matched case-by-case — same input, both sides — not run-total against run-total.
Finer, stronger, and no more expensive.

**Use the suite for cost, the mimic set for behaviour.** This resolves the tension in §2.1:
issue 1's inputs are deliberately edge-heavy and are the wrong basis for a cost number, while
suite cases resemble real inputs.

**Token and cost deltas are solid; latency deltas are not.** The baseline's `latency_ms` was
measured at another hour under different provider load. Latency is advisory unless both sides
are re-measured concurrently.

**Fewer body tokens does not mean cheaper.** A prompt drives cost three ways: its own body (paid
every call), the *output length it induces*, and the model it binds to. Output tokens are
typically priced 3–5× input tokens and the prompt shapes them directly — drop *"trả lời ngắn
gọn"* while trimming the body and the candidate is smaller *and* dearer per call. A static size
comparison is an instant signal, never the answer.

The dispatching half reuses `evaluation.gate.score_body_against_suite`
(`src/prope/evaluation/gate.py:204`), which already does this for `prompt_improvement`: takes a
`CandidateRevision`, runs A's suite, **writes no rows**, and checks the spend ceiling before the
first case. Nothing new is built; `GateResult` gains cost, latency and binding fields.

Prompt size is the free half. **Reuse `prompt_readiness.rules`'
`CHARACTERS_PER_TOKEN`** — the module already estimates a body's token cost at roughly four
characters to the token and documents the reason for not taking a tokenizer dependency, and it
already labels the result `approx_tokens`. A second estimator would be a second answer to
"what does this prompt cost." Note the standing caveat: four-characters-to-the-token is
calibrated for English, and Vietnamese with diacritics tokenizes worse per character in most
BPEs while ADR-0053 makes Vietnamese the default. Exact counts are available from the dispatch
usage when issue 3 runs; the estimate is for the instant answer only, and the two must never be
rendered as the same number.

**A binding change dwarfs both.** If B binds to a different upstream model, that swamps body
size and output length together. Hold the model constant, or report the binding change as its
own line — never fold it into one number. *"23% cheaper"* that is really *"you switched to a
cheaper model"* tells a reviewer nothing about the prompt.

#### Quality — the hard half, and it is smaller than it looks

**The suite cannot measure quality today, and that has to be said plainly.** Every
`AssertionType` is deterministic — `exact`, `substring`, `regex`, `json_schema`,
`required_phrase`, `forbidden_phrase`, `max_length`, `max_latency`, `max_cost`, `asset_count`,
`asset_type`. There is no semantic assertion. So the suite measures **conformance**: an answer
that is factually wrong but carries the required phrase passes.

**The reframe that makes it tractable: issue 3 asks for a delta, not a level.** *"Có giảm chất
lượng không"* — did it get *worse*. Absolute quality assessment is the hard problem. "Worse than
the revision already approved and already in production" has a reference, and the reference is
on disk: **`CaseResultRow.output_content` stores A's actual output text for every case.** So the
quality delta costs **no extra dispatch** — B is dispatched once by the gate, and its output is
compared against A's stored output, per case.

How it is judged:

- **Pairwise preference, never absolute scoring.** *"For this input, is B worse than A, and
  how?"* Pairwise comparison is materially more reliable than rating each output 1–5.
- **Position randomised**, or both orders run. Otherwise it measures which slot the judge favours.
- **One pair at a time**, per `eval/retrieval/judge.py`'s established discipline.
- **Gated by the noise floor** (§2.1). A difference inside A-vs-A variance is not a finding.
- **A separate call from issue 1's "same job?"** One judge asked both questions lets each answer
  contaminate the other.

**Rejected: a model-graded `AssertionType` inside the gate.** *"Passes the suite"* is currently a
deterministic, reproducible predicate that a human approval and a database constraint rest on. A
judge that changes its mind between runs makes that predicate unstable, and that trades the most
defensible property of the release control for coverage. The judge stays **outside** the gate —
evidence on the sheet, never a pass/fail. If it is ever to move inside, that is an ADR, not a
feature flag.

**The layer no metric replaces: show the reviewer the matched output pairs.** The core value
already puts the diff, the eval result and the cost delta on one screen. Same input, old answer,
new answer, side by side is the missing fourth panel — and for quality it is worth more than any
score.

#### Output shape

Three deltas, each carrying the basis it was measured on: **conformance** (hard — a case that
passed no longer does), **cost and latency** (soft, with latency labelled advisory), **quality**
(soft, plus the output pairs themselves). Never one number.

Issue 3 is the clearest case for §4's evidence-sheet rule: *"12% cheaper, fails one case in
twenty"* is a trade no agent should make on somebody's behalf.

---

## 3. What the sub-flow hands upward

**Structured, never a prose summary.** Per-case verdicts, an explicit `diverged_on` list, and
**the divergence verbatim** — which input, what A returned, what B returned.

Removing the 0–5 score was right; the score merged "how similar" with "same job," and a scalar
cannot answer both. But **the veto rule must not leave with it.** If the sub-flow emits a
paragraph, the final agent does the aggregating in natural language by a rule nobody can
inspect — the same happy-path-washes-out-the-edge-case problem, relocated somewhere it cannot
be audited. A mean was a bad shape; at least it was reproducible.

If the one finding that mattered arrives as a sentence inside a paragraph about how similar
everything else was, it gets weighed as a sentence. **Summaries are where evidence dies.**

## 4. The final agent

It takes the three sub-flow results and integrates them, which is correct — the three issues
genuinely trade against each other, and "cheaper but slightly different output" is a real
judgment call.

Two constraints on it:

**Some findings are vetoes it cannot trade away.** Different `required_variables` breaks every
existing caller; no cost saving compensates. If the final agent can be argued out of that,
the system can approve a breaking change on its own.

**It emits an evidence sheet, not a verdict.** The core value is that *no prompt reaches
production without a recorded human approval*. An agent that outputs "same job: yes, add as
revision" is producing something that reads as the approval. Same three inputs, different
output shape, and the agent stays on the right side of the line the product is built on.

---

## 5. Still open

**OQ-a — where the `variant` boundary sits.** Six cases decide it, and the labels for
everything downstream depend on them:

1. Same task, different `output_format` (JSON vs prose) — *proposed: `variant`, never `same`.*
   The gateway serves by model name and a consumer parses the output; the shape is a published
   interface.
2. Same task, different model tuning — *proposed: `same`.* This is what provider binding and
   revisions are for.
3. Same task, different language — **user's call.** A `{{variable}}` makes it `same`; baked
   into the body it is an output-contract difference. ADR-0053 may argue for a firmer rule.
4. Same task, different variable set — *proposed: not `same`.* Exposes a gap: adding a
   required variable is a **breaking change to the input contract**, and the registry has no
   notion of a breaking revision. Every existing caller starts getting `MissingVariable`.
5. Superset — *a distinct relation; the right action is unsettled.*
6. Same task, different `constraints` — *proposed: not substitutable.* The case a whole-document
   embedding is least able to see: the blocks are nearly identical and the difference is a few
   lines.

**OQ-b — how two prose outputs are compared.** Mechanical for a structured `output_format`;
for prose it is fuzzy equivalence one level down, and "same decision, different wording" must
count as equal or every pair fails. Unknown what share of the corpus has a structured
`output_format`.

**OQ-c — the vector floor.** `VECTOR_FLOOR = 0.25` sits at the bottom of the 0.25–0.50 band a
single-genre corpus occupies, so it admits nearly everything. Cannot be picked a priori and
must be calibrated **after** the representation is fixed, against a labelled set, at roughly
the 95th percentile of the hard-negative distribution.

**OQ-d — is 2a a block or a warning?** A revision that adds a required variable breaks every
existing caller. Whether the registry refuses the save, or warns and lets the author proceed,
is undecided. It exposes a gap either way: the registry has **no notion of a breaking
revision** (§5 item 4), so today the approval flow cannot distinguish one from a wording change.

**OQ-e — who owns the output descriptor.** It is a property of a revision that
prompt-readiness, this dedup flow, and prompt-improvement all want. That argues for
prompt-registry owning it rather than `prompt_search` bolting a column onto its index row — but
the module map decides, not convenience.

**OQ-f — output format declared in `<instructions>`.** Real prompts state the output contract
in the instruction block rather than in `<output_format>`. Proposed: read both, but record
which block it came from, since a contract stated only in `instructions` is weaker evidence and
is arguably a readiness finding in its own right. Not decided.

**OQ-g — fresh baseline, or the stored one?** `latest_completed_run` has no age filter, so a
three-month-old run is compared exactly like this morning's, and provider-side snapshot drift
then reads as a prompt regression. Re-running A's suite concurrently removes the drift and
doubles the case count. `prompt_improvement` lives with the stored baseline; the import-time
stakes may differ.

**OQ-h — what happens when A has no suite.** Quality is then undefined for that prompt: no claim
in either direction is available (§1.5). Undecided whether issue 3 is simply absent from the
evidence sheet, or whether its absence is itself a finding the reviewer is shown — *"this prompt
has never been measured"* is arguably the most useful thing on the screen.

**OQ-i — spend and permission.** Issue 1 costs 2N dispatches and issue 3 runs a suite
(`MAX_CASES_PER_SUITE = 20`, `PER_RUN_CONCURRENCY = 5`, `CASE_DEADLINE_MS = 60_000`) on the
workspace's credential, using the *existing* prompt's provider binding. Whether "may read
prompt X" implies "may spend on X's provider config" is unverified — assume it does not.
Neither may run synchronously inside the import dialog, which already sits at 25 s.

## 6. Immediate, independent of all the above

`SimilarPromptsDialog.tsx:39` preselects `matches[0]`, so with a false positive the **default**
action is attaching an incoming prompt as a revision of an unrelated one, and confirm is the
path of least resistance. Default to "create new" until a verdict is `same`.

## 7. The blocker — **cleared**

> No labelled set exists, so no threshold, rubric or verdict boundary can be justified and
> every proposal in §5 is an assertion.

It exists now: `eval/retrieval/similarity.py`, ten triplets — **anchor, twin, decoy** — one
topic each, 20 labelled pairs. Six are entirely real prompts from `playgrounds/prompts/`;
four pair a real anchor and a real decoy with a written paraphrase, because the
professional-persona files in the library have no genuine twin and writing one makes
vocabulary the single moving part. Disagreements are recorded in each pair's `why` and are
now rubric lines, as §7 asked. Two lanes read it: `-m golden` (free, in `make test`) and
`make golden-live` (one model call per triplet).

**What it found immediately, none of which was visible before.**

**The corpus was 2.7% indexed.** 370 prompts, 10 index rows — `seed_prompts.py --index`
defaults to 40 and is capped on purpose, and re-running skips existing prompts and therefore
queues nothing. `seed/backfill_index.py` fixes the state; the recall ceiling §2.0 calls a
prerequisite is still not reported per workspace.

**The pre-filter was a length sort.** Containment divides by the *incoming* prompt's term mass
and never charges a candidate for its own size, so the four longest documents in a
twenty-candidate pool took four of the top five places for every incoming prompt regardless of
subject — a 20 k prompt about removing AI tells from prose outranked `clinical_assistant` for
an incoming clinical prompt. Two of ten twins never reached the adjudicator. `FOCUS_EXPONENT`
(0.35, the smallest value that seats 10/10) multiplies the ranking by the share of the
*candidate's* own mass the overlap accounts for. Ordering only; `match` still means coverage.

**The 90% floor could never have fired.** Every one of the ten confirmed duplicates scores
below it; the best reaches **0.472**. The number was inherited from A-S153, where *"90%
similarity"* is a **cosine** behind a non-blocking index-time warning — a different scale,
which on this corpus also never reaches 0.9. Twin and decoy `match_score` ranges *overlap*, so
no lexical threshold separates them at any value. The floor therefore no longer governs
`same`, `supersedes` or `variant`; it governs `related` context rows and its default is 0.25,
just above the highest near-miss observed.

**The adjudicator was being shown 1,200 characters of prompts up to 23,925 long** — 2.8% of
one of them — and its commonest error was `same_task` answered as `candidate_narrower`, which
is a model correctly reporting what it was given. At 4,000: recognised duplicates 4 → 7,
that error 4 → 1, decoys called `same_task` **0 at both**.

**Two bugs the fail-soft paths had been hiding.** `descriptor_of` read the model's `keys`
field with `getattr`, which on a `dspy.Prediction` returns the bound mapping method — every
extraction raised `TypeError`, was swallowed, and **stage 2b had never once run** since
migration 0035. And `present()` returned `""` for a canonical prompt whose content sits
outside `instructions`/`output_format`/`constraints`; asked to compare a real prompt against
nothing, the adjudicator answered `same_task`, which resolves to `SAME` — §1.5's unrecoverable
recommendation, produced by an empty string.

That second bug had been holding three integration tests up. `test_prompt_search_similar.py`
seeds every revision with `seed_revision`'s default `"You are a helpful assistant."` and asks
the route about *"Classify the refund request."*; with `present()` returning `""` the
adjudicator answered `same_task`, the rows stayed on the sheet, and three assertions about
**retrieval** — the index is not a gate, the nearer vector ranks first, an actor cannot rank
what they may not read — passed on a verdict nobody had set up. Fixing `present()` made the
adjudicator answer `different`, correctly, and all three failed. They now stub the
adjudication at `same_domain`, on the same argument the `no_match_floor` fixture already
makes one rung lower: a retrieval property may not depend on what a model makes of a fixture
body. It also takes three live model calls out of the integration suite, which runs in 84 s
instead of 343 s.

**And fixing the bug was not enough to make stage 2b run, which took a second look to
see.** With descriptors finally being written, the rung still reported *not established* on
every import, because it needs **both** sides and the incoming side was structurally
unreachable: `declared_output_text` reads `<output_format>`, falls back to `<instructions>`,
and returns `("", unspecified)` for anything that is not canonical XML — while the duplicate
check runs *before* conversion (`usePromptImportFlow`: `similar` → `convert`), so what it
holds is always prose. The refusal was deliberate and its reasoning was sound in isolation:
guessing a contract out of unstructured text is the fuzzy step the stage exists to avoid.
Measured against the running system it cost more than it saved — a rung that cannot fire is
not a strict rung, it is an absent one.

So stage 2b now **fills its own gaps** rather than reporting them:

- `declared_output_text(body, allow_prose=True)` hands the whole body to the extractor under
  a third `source_block`, `whole_text`, and `compare_output_contracts` emits
  `similar.output_contract.inferred_from_prose` so the sheet says which of the three sources
  a contract came from instead of flattening them. It is INFO, never HARD: it reports how
  well the contract is known, not that anything about it breaks.
- `compare()` takes an injected `describe` and extracts what the index could not supply —
  the incoming body always, and any shown candidate whose row carries no descriptor for the
  revision being compared. It runs **after** adjudication, in one gathered batch, so a
  candidate the adjudicator called `different` never costs a call: output findings only
  demote, and that candidate has already left the sheet.
- Whatever comes back is written to the index row it was missing from
  (`repository.cache_output_descriptors`, guarded on `version_id` and on the column being
  `NULL`, so it can neither attach a descriptor to the wrong revision nor overwrite the
  indexer's stricter answer). The second import of the same neighbourhood pays nothing.

**What it changed on the pair that started all this.** Before: four candidates, all `same`,
every one carrying `output_contract.not_established`, and `recommend()` declining to
pre-select anything because four `same` rows is an unresolved question. After, on the same
paste: `contracts` reports `hard: 5, demoted: 2`, and the sheet reads `same` for the twin,
`supersedes` for one neighbour, and **`variant` for two** — demoted on `modality_changed` and
`keys_missing`, which is exactly what `variant` was defined to name. Latency 10–11 s.

**What the two lanes read after all of it.** Offline: 10/10 twins survive every free rung,
no decoy is ever called a duplicate, and the shipping floor hides no confirmed duplicate.
Live, one real adjudication per triplet: **9 of 10 twins judged same-job**, **1 of 10 decoys
called `same_task`** — t04's `security_researcher`, which is the same pair as the asymmetry
below and not a second problem. One decoy, t03's, never reached the adjudicator at all: the
pre-filter cut it, which is the cheaper of the two right answers. The assertion is written as
`<= 1` rather than `== 0` deliberately: adjudication is the only probabilistic rung, and
contract compatibility is decided in code beneath it. The characters-seen column also shows
what the 4,000 budget still cannot reach — t10's anchor is 23,925 characters and the
adjudicator sees 4,033 of them.

**`same_task` is not symmetric in practice, and this is the sharpest open problem.** t04 is
the standing example: asked `code_reviewer_security` → `security_researcher` the adjudicator
answers `same_task`; asked the reverse, through the real route, it answers `related` with
`different_action, different_object`. Their output contracts settle which is right — one is
keyed to `File:LineNumber` and quotes the offending source, the other to a component with a
CVSS vector and detection guidance — so the label stands and the model over-calls in one
direction only. §1.1 already says substitutability *is* asymmetric and that a cosine cannot
represent it; what this shows is that `same_task` is being used as though it were symmetric
when the model does not treat it that way. The relation vocabulary has no way to say *same
job, different output shape* — that is `variant`, a verdict the contract check derives — so
stage 2b is what has to catch it, and it can only do so once descriptors exist.

**Still open.** OQ-c is not closed: the set calibrates the display floor, not `VECTOR_FLOOR`,
which needs a retrieval-side sweep. The set is ten triplets, not the thirty pairs §7 asked
for. The per-block share in `present()` is now a reservation rather than a ceiling — a
single-block prompt was being shown `limit // 3` while the rest of the budget went unspent,
which is why a prompt compared against its own stored text read as `candidate_narrower` — but
the two sides are still cut differently (a raw paste flat, a canonical candidate per block),
and that asymmetry has not been removed.

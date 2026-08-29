# 05 — Evaluation

Two levels here, and the distinction is the chapter: **the gate evaluates the candidate prompt;
the meta-eval evaluates the pipeline that produced it.** Prope is an evaluation product, so
level 1 is unusually strong — and it sets a rule the meta-eval must not weaken.

## Level 1 — the gate (evaluating the candidate)

| # | Decision | Value |
|---|---|---|
| D5 | Deterministic first | **Fully honored, structurally.** The gate runs the workspace's own suites through deterministic assertions (regex, schema, phrase, length, latency, cost) — there is **no LLM judge anywhere in the accept path**. A judge cannot approve a wrong number here; there are no judges |
| Gate predicate | For eval-analysis proposals the gate is **strict non-regression + strict improvement**: (a) existing semantics — any baseline-pass case that stops passing, any candidate ERROR, any suite without a baseline that does not fully pass ⇒ **regressed ⇒ discarded**; plus (b) **the finding's own failed count on the target suite must strictly decrease**. A candidate that fixes nothing and breaks nothing is *not* an improvement — it does not survive this gate |
| D9/D12 | Statistical honesty | Raw case counts only — no percentages, no confidence intervals on suite-sized N (a 12-case suite makes one flip read as "8%"). The proposal card shows `failed 5/12 → 2/12` and the accepter sees N. Wilson intervals would be false precision at this size; we quote nothing rather than something wrong |
| D14 | Noise floor | One probe per candidate (cost-bound, matching the existing gate). Temperature of the *target prompt's* provider can flip outcomes run-to-run — this is stated, not hidden: the delta is evidence of improvement, the human accept is the decision, and the release flow re-runs the full suites independently downstream. A k-repeat probe is a recorded follow-up lever if accept-then-regress appears in the online signals |
| D6 | Pinned judge | n/a — no judge exists to pin. The *assertions* are code and the suites are versioned rows; the gate is reproducible from `(suite version, revision, probe config)` — the custom-stack property satisfied |
| Baseline | The baseline is the very run the analysis read (`baseline_run_id` reference, existing convention) — the improvement claim is measured against the evidence that motivated it, not a convenient rerun |

## Level 2 — the meta-eval (evaluating the pipeline)

| # | Decision | Value |
|---|---|---|
| D1 | Layers | Component = rails unit suite (each rail, each failure code) + drafter signature tests. End-to-end = the seeded-prompt golden set (below) through draft→rails→gate. Online = disposition + quality signals on real traffic (D17) |
| D2 | Trajectory | The workflow analog: **redraft rate** (drafts per proposal), rails-failure distribution by code, termination-reason distribution, cost per proposal. A proposal that passes on attempt 3 is a different system from one that passes on attempt 1, and only these make it visible |
| D3/D4 | Golden set | Seeded prompt fixtures — no human labelling bottleneck because the gate labels outcomes deterministically. Slices, named: by finding type (`regex`, `json_schema`, `required_phrase`, `max_length`, `latency`, `cost`, generic), by difficulty (single failing group / multiple groups / conflicting groups), an **unfixable slice** (prompts whose failures an edit cannot fix — the correct outcome is discard-with-reason, *not* a forced proposal), and the adversarial slice from 03-guardrails D15. Target ~10–15 fixtures per finding-type slice at v1 (a tripwire, not a statistic — D11's distinction, stated) |
| D8 | Judge validation | n/a — no judge. The gate *is* the validated grader: it is the product's own assertion engine |
| D10/D11 | CI gate | The rails suite, injection fixtures, gate-discard test, and golden-set run execute on every change to the drafter signature, rails, or gate predicate, and block merge — they live in `pytest` beside the existing `tests/prompt_improvement/` suites (the repo's convention) |
| D15 | pass^k | Not applicable to the artifact (one proposal per run) but applied to the *pipeline*: the golden set reports per-fixture outcomes across N=3 pipeline runs with a fixed draft model, so drafter variance is visible as a rate, not an anecdote |
| D16 | Refresh | Event-triggered, matching the pack default: any draft-model swap (02-D15), rails change, or gate-predicate change re-runs the golden set; the acceptance metrics (below) review quarterly |
| D17 | Online signals | On real traffic, tracked and alerted: `rails_rejected_total` by code (spike = injection or model regression), `gate_rejected_total`, redraft-rate distribution, **accept rate** (04-D15: ~100% accept = rubber-stamp alarm), dismiss-with-reason themes, cost per proposal on both meters, and the long-run signal: **do accepted revisions' subsequent eval runs pass more than their baselines?** — measurable because Prope tracks runs per version; this retention analysis is the true north metric and a recorded follow-up once the first acceptances exist |
| D18 | Eval cost | The golden set spends draft tokens (Prope's meter) + probe spend (workspace's meter) — capped per run (01-D8); tracked as `improvement_draft_cost_usd_total` and existing probe metrics; the suite's cost trend is on the same dashboard |
| D19 | Public benchmarks | Not used. The gate is the task-distribution-matched set by construction |

## Failure modes → what catches them

| Failure | Catch |
|---|---|
| Gate measures suites, not intent | known residual (03); human diff review is the control — never auto-accept (04-D4) |
| Small-N overconfidence | raw counts, no intervals, N displayed (D12 row above) |
| Noise flip accepted as improvement | stated noise caveat + online retention signal catches it after the fact; k-repeat probe is the lever |
| Drafter variance hidden | 3-run golden-set variance reporting (D15 row) |
| Rubber-stamped acceptances | accept-rate alarm (~100%) |
| Golden set drifts easy | unfixable + adversarial slices are permanent members; refresh is event-triggered on model/rails changes |

## Readiness checks

| ID | Sev | Assertion | Status |
|---|---|---|---|
| E1 | blocker | Suite runs on every pipeline change, blocks merge | pytest placement, existing convention |
| E2 | blocker | No numeric/safety claim graded by a judge | no judge exists |
| E3 | blocker | Grader pinned/reproducible | suites versioned; gate = code + suite version + revision |
| E4/E5 | high | Judge κ / swap augmentation | n/a — no judge; recorded |
| E6 | high | Retrieval vs generation separated | n/a — no retrieval; recorded |
| E7 | high | Golden set refreshed / event-triggered | D16 triggers named |
| E8 | high | Noise floor measured | 3-run variance on golden set; probe noise stated |
| E9 | med | Named slices, per-slice reads | slice table above |
| E10 | med | Canary replay on cadence | golden set re-runs on trigger; canary = unfixable + adversarial slices |
| E11 | med | Online signals with alerting | disposition + rails/gate rates + accept-rate alarm |
| E12 | med | pass^k reported | 3-run pipeline variance (D15 row) |
| E13 | med | Eval cost tracked | both meters, per suite run |
| E14 | low | Wilson-or-nothing intervals | nothing quoted — counts only |

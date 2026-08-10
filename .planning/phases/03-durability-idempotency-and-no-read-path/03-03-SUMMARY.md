---
phase: 03-durability-idempotency-and-no-read-path
plan: 03
subsystem: backend
tags: [prometheus, pydantic, fastapi, observability, security, tenancy]

# Dependency graph
requires:
  - phase: 01-data-model-pricing-and-retention
    provides: "ck_workspace_retention_window_is_positive — the LOWER bound on a retention window, which stays at the engine and is the half this plan does not touch"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 04
    provides: "seams.check_spend_ceiling — the fail-open branch, CeilingDecision's two fields, CeilingReason, _UnevaluableCeilingError, and tests/integration/test_ceiling_refuses_evals_only.py"
  - phase: 02-seams-enqueue-the-broker-drain-and-the-ceiling
    plan: 05
    provides: "schemas.RetentionSet, ErrorCode as a closed StrEnum, install_error_envelope's RequestValidationError handler, api.set_retention, and test_management_routes.py's dependency_overrides test seam"
  - phase: 03-durability-idempotency-and-no-read-path
    plan: 01
    provides: "observability.ceiling_check_total defined at import with labelnames=(\"result\",), and ceiling_failed_open_total carrying the #: line saying this plan retires it"
provides:
  - "seams.CeilingCheckResult — the closed three-value metric label vocabulary, chosen in one place"
  - "ceiling_check_total{result} incremented on ALL FOUR returns of check_spend_ceiling — allowed ×3, refused ×1 — plus failed_open in the except handler"
  - "schemas.MAX_RETENTION_DAYS = 3650 and RetentionSet.retention_days = Field(le=MAX_RETENTION_DAYS)"
  - "tests/unit/test_retention_days_bound.py — the bound asserted as a PROPERTY (the OverflowError is unreachable through the schema), not only as a number"
  - "Removed: prope_call_ledger_ceiling_failed_open_total — definition, import and increment"
affects: [03-04-metrics-route-and-alerts, 16-18-evaluation, 07-identity-and-session]

actuals:
  tokens: 44000
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns:
    - "A metric label vocabulary as a StrEnum beside the seam it labels, NOT in domain.py — domain.py holds the vocabularies the database has CHECK sets for, and no column carries this one"
    - "Exhaustiveness asserted by SUMMING the deltas of every label value across one call, so a single increment keyed off a boolean cannot pass"
    - "An increment placed immediately before its own return rather than once at the end, because two branches share a return VALUE and only the branch identity is the signal"
    - "A bound whose test asserts the exception it exists to prevent is unreachable, constructed from the constant, so a retune cannot reintroduce the bug the number was chosen to close"
    - "A documented exception to build-database-first, named at the field, with the instruction not to tidy one bound into the other's home"

key-files:
  created:
    - tests/unit/test_retention_days_bound.py
  modified:
    - src/prope/call_ledger/seams.py
    - src/prope/call_ledger/schemas.py
    - src/prope/call_ledger/api.py
    - src/prope/observability.py
    - tests/integration/test_ceiling_refuses_evals_only.py
    - tests/integration/test_management_routes.py

key-decisions:
  - "CL-07 was closed by giving allowed and refused the increment sites they never had — three new sites out of four — and not by renaming a constant. A rename would have left two of the three declared label values permanently at zero"
  - "The result vocabulary is a StrEnum (CeilingCheckResult) in seams.py beside CeilingReason, not module-level string constants and not in domain.py: it is a metric label set, not a stored status, and domain.py's rule is that it holds the vocabularies the database has CHECK sets for"
  - "The refused branch increments AFTER its log.info rather than before it, so a logging call that somehow raised takes the fail-open path alone and cannot contribute a second increment to the same call. The three allowed sites and the failed_open site have no statement between increment and return"
  - "The A-056 no-figure assertion's fail-open case is the CURRENCY MISMATCH and deliberately not the exploding sessionmaker: the exploding one never opens a session, so no figure was ever in scope and asserting its absence would assert nothing"
  - "src/prope/call_ledger/api.py was edited outside files_modified (declared drift): its set_spend_ceiling docstring named the retired counter as the live control, and the plan's own acceptance criterion requires grep to find no such name in src/"
  - "The plan's grep-shaped acceptance criteria for `ceiling_failed_open_total` and `ArithmeticError` contradict its own <verification> block and its own <action>; resolved by narrowing each to what it was actually protecting, with both readings recorded below"

patterns-established:
  - "A helper that asserts BOTH 'this label moved by one' and 'the sum of all labels moved by one', so the mutual-exclusivity property is not a separate test somebody can skip"
  - "A test file whose module docstring states which mistaken implementation each assertion refuses, in the implementation's own terms"
  - "A negative control run during execution and recorded in the summary rather than left as a claim — one label deliberately mislabelled, two tests red, reverted"

requirements-completed: [CL-07]

coverage:
  - id: D1
    description: "A spend-ceiling check that cannot be evaluated returns allowed, increments prope_call_ledger_ceiling_check_total{result=\"failed_open\"}, and raises nothing into the caller — ROADMAP SC3, over both unevaluable shapes"
    requirement: CL-07
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_an_unevaluable_check_allows_and_counts_and_does_not_raise"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_ceiling_and_a_spend_in_different_currencies_fail_open"
        status: pass
    human_judgment: false
  - id: D2
    description: "All three label values have an increment site, and exactly one fires per call — asserted as the SUM of the three deltas across a single check, over all six branches"
    requirement: CL-07
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_workspace_with_no_ceiling_row_is_allowed"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_disabled_ceiling_allows_however_far_over_the_spend_is"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_an_enabled_ceiling_with_no_priced_spend_this_month_is_allowed"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_a_workspace_under_its_ceiling_is_allowed"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_gateway_traffic_alone_over_the_ceiling_refuses_with_a_reason"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_spend_exactly_at_the_limit_refuses"
        status: pass
    human_judgment: false
  - id: D3
    description: "The result vocabulary is closed at three values, chosen in exactly one place, and the label values a rules file will match on are pinned by spelling"
    requirement: CL-07
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_the_result_vocabulary_is_the_three_values_the_lock_file_declares"
        status: pass
      - kind: manual
        ref: "grep -rn '\"allowed\"|\"refused\"|\"failed_open\"' src/ — each literal appears exactly once, at its CeilingCheckResult member"
        status: pass
    human_judgment: false
  - id: D4
    description: "No spend, limit, remainder or currency code reaches the serialized decision or any captured log record under ANY branch — refused, allowed, and failed open"
    requirement: CL-07
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_no_figure_reaches_the_decision_or_a_log_line_under_any_branch"
        status: pass
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_the_decision_has_exactly_two_fields_and_a_typed_reason"
        status: pass
    human_judgment: false
  - id: D5
    description: "Gateway traffic for a workspace over its ceiling is still recorded normally — the ceiling governs eval runs only (A-029)"
    requirement: CL-07
    verification:
      - kind: integration
        ref: "tests/integration/test_ceiling_refuses_evals_only.py::test_gateway_traffic_keeps_being_recorded_after_the_refusal"
        status: pass
    human_judgment: false
  - id: D6
    description: "prope_call_ledger_ceiling_failed_open_total no longer exists in the registry, and nothing in src/ references it outside the one comment recording the retirement"
    verification:
      - kind: manual
        ref: "grep -rn 'ceiling_failed_open_total' src/ --include=*.py — two lines, both inside one comment block in observability.py; the Counter object is gone"
        status: pass
      - kind: integration
        ref: "tests/broker/test_publish_confirm_failures.py::test_workspace_id_is_never_a_metric_label — the REGISTRY.collect() cardinality walk still passes with the metric set changed"
        status: pass
    human_judgment: false
  - id: D7
    description: "A retention_days value above the bound is refused as a 422 carrying the EXISTING VALIDATION_FAILED code, before any timedelta is constructed, and stores nothing"
    verification:
      - kind: integration
        ref: "tests/integration/test_management_routes.py::test_a_window_above_the_bound_is_a_422_and_stores_nothing"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py::test_the_largest_window_the_bound_allows_still_takes_effect"
        status: pass
      - kind: unit
        ref: "tests/unit/test_retention_days_bound.py::test_one_day_past_the_bound_is_refused_by_name"
        status: pass
      - kind: unit
        ref: "tests/unit/test_retention_days_bound.py::test_the_bound_adds_no_error_code"
        status: pass
    human_judgment: false
  - id: D8
    description: "No retention_days value accepted by the schema can make timedelta(days=...) raise OverflowError — asserted as the property, derived from MAX_RETENTION_DAYS, with the real OverflowError provoked in the same test so the schema's refusal is not mistaken for its absence"
    verification:
      - kind: unit
        ref: "tests/unit/test_retention_days_bound.py::test_the_overflow_this_bound_exists_to_prevent_is_unreachable_through_the_schema"
        status: pass
      - kind: unit
        ref: "tests/unit/test_retention_days_bound.py::test_the_largest_accepted_value_validates"
        status: pass
    human_judgment: false
  - id: D9
    description: "The LOWER bound is still the database's: 0 and -1 validate at the model and are refused at the engine, and the field says why the upper one could not live there"
    verification:
      - kind: unit
        ref: "tests/unit/test_retention_days_bound.py::test_a_non_positive_window_is_still_accepted_by_the_model[0]"
        status: pass
      - kind: unit
        ref: "tests/unit/test_retention_days_bound.py::test_a_non_positive_window_is_still_accepted_by_the_model[-1]"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py::test_a_non_positive_window_is_refused_and_stores_nothing[0]"
        status: pass
      - kind: integration
        ref: "tests/integration/test_management_routes.py::test_a_non_positive_window_is_refused_and_stores_nothing[-1]"
        status: pass
    human_judgment: false
  - id: D10
    description: "ROADMAP SC3's words are 'increments the failed-open counter' and this plan ships that as a LABEL VALUE on the declared metric, retiring the Phase 2 constant of that name"
    verification: []
    human_judgment: true
    rationale: "The mechanical half is fully asserted — the branch counts, on result=\"failed_open\", and raises nothing. What a human must confirm is the READING: that a labelled counter is a counter, so SC3 is not scored against a constant that no longer exists. It is the plan's first <human-check>."
  - id: D11
    description: "MAX_RETENTION_DAYS = 3650 is a product-visible limit — no workspace can set a retention window longer than ten years through the API"
    verification: []
    human_judgment: true
    rationale: "The number is argued at the constant in the house form and asserted from both sides, but 'is ten years the right cap' is a product judgement, not a property a test can settle. It is the plan's second <human-check> and is already deferred-items.md Part 1 item 4."

# Metrics
duration: 55min
completed: 2026-08-11
status: complete
---

# Phase 03 Plan 03: Durability, idempotency, and no-read-path Summary

**CL-07 is closed, and it was not closed by renaming a constant.** Phase 2 shipped the fail-open
branch and wrote at the code that the *claim* was not its own. What actually stood between the branch
and the requirement was the metric: the lock file declares
`prope_call_ledger_ceiling_check_total` labelled `result = allowed | refused | failed_open`, which
counts **every** check, and only the open failure had an increment site. **Three of the four sites
were missing and this plan added them** — `allowed` on all three of its branches, `refused` on the
one that refuses — and retired Phase 2's `prope_call_ledger_ceiling_failed_open_total` so that one
number does not have two names.

**CR-01 is closed at the boundary.** `retention_days` now carries `le=MAX_RETENTION_DAYS`, and the
paragraph beside it says why that bound cannot live where every other bound in this repository lives.

## Performance

- **Duration:** ~55 min
- **Tasks:** 2
- **Files created/modified:** 7 (1 created, 6 modified — one of them undeclared; see Deviations)
- **Test suite:** **337 passed**, 0 failed (326 at the 03-02 baseline; +11)

## `ceiling_check_total{result="failed_open"}` **is** ROADMAP SC3's failed-open counter

The plan's `<output>` requires this in the summary's own words, so it is stated in full and it is the
first thing the verifier should read.

SC3 says *"a ceiling check that cannot be evaluated returns allowed, **increments the failed-open
counter**, and does not raise into evaluation"*. There is no longer a metric named
`prope_call_ledger_ceiling_failed_open_total` in this codebase. That is not an omission and it is not
a partial close.

**A labelled counter is a counter.** `prope_call_ledger_ceiling_check_total{result="failed_open"}` is
the same number Phase 2's constant held, under the name the lock file declares and the name plan
03-04's six alert rules will be written against. Scoring SC3 against the retired constant would score
it against a name the spec never contained.

What the label buys, and why it is strictly better than the constant it replaces: **a failed-open
count is unreadable on its own.** Fifty open failures is a catastrophe against a thousand checks and
a rounding error against ten million, and the Phase 2 counter could not tell those apart because
nothing counted the denominator. Three mutually exclusive, jointly exhaustive label values give
`failed_open / sum(ceiling_check_total)` — a rate, which is what an alert can be written against.
**That is why "give `allowed` and `refused` increment sites" is the requirement's actual work rather
than bookkeeping.**

## Why the increments sit beside each `return` and not once at the end

The tempting implementation is one `.inc()` at the bottom keyed off `decision.allowed`. It is wrong
for a specific, checkable reason: **`allowed` is `True` on two different branches** — the workspace
was under its ceiling, and the check could not be evaluated at all — so a boolean cannot separate
them, and `failed_open` is the one value the whole control exists for. That implementation would have
reported every open failure as an ordinary allow, and the number would still have risen, on the wrong
label, invisibly.

`test_ceiling_refuses_evals_only.py` refuses it directly. Every check-driving test now reads all
three label values before and after and calls `_assert_counted_once`, which asserts **two** things:
its own value moved by exactly one, *and* the **sum** of the three deltas is exactly one. The second
assertion is the one that kills the boolean implementation.

Two placement details, both written at the code:

- The **refused** branch increments *after* its `log.info`, not before, so a logging call that somehow
  raised would take the fail-open path alone and could not contribute a second increment to the same
  call. The three `allowed` sites and the `failed_open` site have no statement at all between the
  increment and the return.
- The counter counts **branches** and carries no figure — no spend, no limit, no remainder, no
  currency code, and no `workspace_id`. That is what makes the ceiling observable while
  `CeilingDecision` keeps exactly two fields (A-056). *"Add observability to the ceiling"* is exactly
  the change that would otherwise have arrived carrying a `remaining` field, and it is said at the
  refusal branch because that is where it would be added.

## Why CR-01's bound is the documented exception to build-database-first

The plan's `<output>` requires this too.

This repository's standing rule is that **the migration carries the guarantee** — constraint,
privilege, policy, grant, trigger — and application code is what the guarantee protects. The lower
bound on a retention window obeys it: `ck_workspace_retention_window_is_positive` refuses a zero or
negative window at the engine, `set_retention_window` surfaces that refusal rather than clamping, and
`RetentionSet`'s existing paragraph arguing the deliberate absence of a pydantic lower bound is
**unchanged in substance** by this plan.

The upper bound is different in kind, and the difference is mechanical rather than stylistic:
`api.set_retention` evaluates `timedelta(days=payload.retention_days)` **before any statement
exists**. Above `timedelta.max.days` (999,999,999, verified on this interpreter) that expression
raises `OverflowError`, which subclasses `ArithmeticError` and matches **none** of
`classify_write_failure`'s branches — so it takes the `PERMANENT` default and dead-letters, two
modules away from the route that accepted the value. **A `CHECK` cannot refuse an exception raised in
the client before a statement is constructed.** There is no engine at that point to be database-first
about.

So the bound goes on the field, and the reason is written **at the field**, ending with the
instruction that is the whole point of writing it: a later reader must not tidy either bound into the
other's home, because they are one field's two bounds held in two places for two different reasons.

**What this plan deliberately did not do:** add an `ArithmeticError` branch to
`classify_write_failure`. That would treat a bad input as a write-classification problem two modules
from where it was accepted, and it would soften a classifier whose `PERMANENT` default is load-bearing
(T-02-06). `src/prope/call_ledger/drain.py` is byte-identical to what plan 03-02 left.

## What shipped

**`src/prope/call_ledger/seams.py`** — `CeilingCheckResult`, a three-member `StrEnum` beside
`CeilingReason`. It is **not** in `domain.py`, and the reason is written at the class: `domain.py`
holds the vocabularies the database has `CHECK` sets for, and no column carries this one — it is a
metric label set that leaves the process on a Prometheus series and nowhere else. It follows
`enqueue._classify_publish_failure`'s discipline: one place a value is chosen, so a fourth cannot
appear by accident. Four increment sites inside `check_spend_ceiling`, one in the `except` handler.
The import moved from `ceiling_failed_open_total` to `ceiling_check_total`. Two docstring paragraphs
were rewritten rather than left standing: the fail-open paragraph now names the labelled metric, and
*"the branch ships here; the claim does not"* is replaced by what CL-07 now asserts, in the
requirement's own three clauses, plus the corollary about SC3's wording said out loud.

**`src/prope/observability.py`** — `ceiling_failed_open_total`'s `Counter` is deleted. The registry
now holds exactly the eighteen the module docstring declares. Two things moved rather than being
deleted with it:

1. The *"an open-failing check nobody watches is an off switch, so the mitigation for T-02-26 is this
   counter rather than the branch"* argument, onto `ceiling_check_total`'s `#:` block. It is an
   argument about why the **branch** is allowed to exist, so it survives the counter it was written
   under.
2. A short comment block where the constant used to be, recording that the retirement happened, that
   it was **not** kept alongside (two names for one number fail by one of them stopping being
   incremented in a refactor nobody reviews for that) and **not** aliased (`prometheus_client` has no
   alias primitive, so an alias is a second `Counter` incremented beside the first — "keep alongside"
   with a nicer word on it). It exists so that an operator meeting the old name in a dashboard or an
   old plan finds out where it went in one grep.

`ceiling_check_total`'s `#:` block also disambiguates `result` explicitly, in the shape
`enqueued_total`'s `outcome` comment established: **it is a third vocabulary** — not `domain.Outcome`
(a call's fate), not `enqueued_total`'s `outcome` (a handoff's fate), but the fate of one **check** —
because a reader who has met the other two will otherwise assume this is one of them.

**`src/prope/call_ledger/schemas.py`** — `MAX_RETENTION_DAYS = 3650` beside `MAX_PAGE_LIMIT`, for
that comment's stated reason (the test asserts the number, and a literal in a `Field` is a number a
test would have to restate), with the ten years argued rather than rounded and with what the bound
does **not** do stated: it bounds what a caller may *set*, never what the column may *hold*.
`retention_days: int = Field(le=MAX_RETENTION_DAYS)`. `ErrorCode` gains no member — `git diff` shows
no change inside that class — and the field says why: a `le=` violation renders as the existing
`VALIDATION_FAILED` through `install_error_envelope`'s `RequestValidationError` handler, and a new
code would be one the SPA's catalogue has never seen (ADR-0053), which renders as nothing at all and
does so silently. `MAX_RETENTION_DAYS` was added to `__all__` alongside the two page-limit constants.

**`tests/unit/test_retention_days_bound.py` (new)** — six tests. The boundary pair; the **property**
(`timedelta(days=MAX_RETENTION_DAYS)` constructs, the real `OverflowError` is provoked at `10**9` so
the exception is proved to exist, and then `RetentionSet(retention_days=10**9)` is shown to raise
`ValidationError` **first**); the negative control that `0` and `-1` are **accepted** by the model
because the lower bound is the engine's, with the instruction in its docstring that if it ever starts
failing somebody has moved the lower bound into pydantic and the field's paragraph must be deleted in
the same change; the constant pinned at 3650; and the no-new-`ErrorCode` assertion.

**`tests/integration/test_ceiling_refuses_evals_only.py`** — the delta helpers now read all three
label values; six tests gained the exactly-once assertion; three tests are new (the empty-month
branch, which had no case of its own and is one of the four evaluated paths; the closed-vocabulary
pin; and the fail-open half of the no-figure assertion). The no-figure test grew from two branches to
three and now searches for `VND` as well, because on the currency-mismatch branch the row **has been
read** and both currency codes are live in the function's locals when the exception is raised.

**`tests/integration/test_management_routes.py`** — the over-the-bound `422` through the real route
with the session dependency overridden, its positive control at exactly the bound, and one docstring
corrected to the new metric name.

## The empty-month branch had no test, and that is worth naming

`check_spend_ceiling` has four evaluated paths and the file asserted three. The missing one is *a
ceiling row exists and no priced traffic has landed this month* — the `LEFT JOIN`'s own branch, whose
whole reason for existing is that an inner join would have collapsed it into "no ceiling configured",
and the two are opposite states. A counter added to three of the four sites would have passed the
existing file. It is now `test_an_enabled_ceiling_with_no_priced_spend_this_month_is_allowed`, and it
asserts the `workspace_spend` row really is absent before it calls, so the branch it names is the
branch it takes.

## The negative controls, run rather than claimed

Two, both executed during this plan and then reverted:

| Deliberate break | What went red |
|---|---|
| The `refused` site relabelled to `CeilingCheckResult.ALLOWED` | `test_gateway_traffic_alone_over_the_ceiling_refuses_with_a_reason` and `test_spend_exactly_at_the_limit_refuses` — **2 failed, 12 passed**, with the delta dict printed in the message |
| `Field(le=MAX_RETENTION_DAYS)` reverted to a bare `int` | `test_one_day_past_the_bound_is_refused_by_name` and `test_the_overflow_this_bound_exists_to_prevent_is_unreachable_through_the_schema` — **2 failed, 5 deselected** |

Both were restored and the full run below is against the restored tree. The first is the one that
matters: it is the exact mistake the mutual-exclusivity assertion was written to catch, and the
failure message named the wrong label rather than merely failing.

## Deviations from Plan

### Declared drift — a file outside `files_modified`

**1. `src/prope/call_ledger/api.py`**

- **Found during:** Task 1, running the plan's own acceptance grep.
- **Issue:** `set_spend_ceiling`'s docstring named `prope_call_ledger_ceiling_failed_open_total` as
  the live control behind its *"a limit with no currency is refused"* argument — the sharpest
  paragraph in that route. Retiring the counter makes the sentence name a metric that does not
  exist, and the plan's own acceptance criterion is that `grep -r "ceiling_failed_open_total" src/`
  finds nothing. The plan anticipated the retirement but did not list this file.
- **Fix:** one sentence, rewritten to
  `prope_call_ledger_ceiling_check_total{result="failed_open"}`. The same edit also corrected *"a
  counter that has no scraper until Phase 3"* to *"until plan 03-04 mounts `/metrics`"*, since Phase
  3 is now, and 03-04 is the plan that actually closes it. **No code changed in this file** and the
  route's behaviour is untouched.
- **Verification:** `tests/integration/test_management_routes.py` — 34 passed within the 40-test run.

### Two acceptance criteria that contradict the plan's own instructions, and how each was read

Neither is a deviation from the plan's *intent*; both are grep-shaped proxies that the plan's
`<action>` and `<verification>` blocks make unsatisfiable as literally written. Recorded in full so
that a verifier running them sees the same thing this executor did.

**2. `grep -r "ceiling_failed_open_total" src/` returns nothing**

The `<action>` requires the retirement to be recorded at the code and the `<verification>` block says
the grep should return nothing *"outside a comment recording the retirement"*. The two cannot both be
satisfied literally. **Resolution: exactly one comment block, in `observability.py`, where the
constant used to be defined.** Every other mention in `src/` was reworded to *"Phase 2's separate
fail-open counter"* so the symbol itself appears in one place and one place only. The grep returns two
lines, both inside that single block, one of them the full metric name an operator would search for.
**The `Counter` object is gone from the registry**, which is what the criterion was protecting.

**3. `grep -r "ArithmeticError" src/` produces no output**

The same criterion's own text says what it is really asserting: *"`src/prope/call_ledger/drain.py`
gains no `ArithmeticError` branch"*. But the plan's `<verification>` block **requires** the new
paragraph at `RetentionSet` to name `OverflowError`, `ArithmeticError` and `classify_write_failure`
by name — so the repo-wide grep cannot be empty if the plan is followed. **Resolution: the narrow
form.** `grep -rn "ArithmeticError" src/prope/call_ledger/drain.py` returns nothing and exits 1;
`git diff` on `drain.py` is empty. The one repo-wide hit is the required docstring in `schemas.py`.

### Auto-fixed issues

**4. [Rule 2 — a declared export list that would have gone stale] `schemas.__all__`**

- **Found during:** Task 2.
- **Issue:** `schemas.py` maintains an explicit `__all__` that lists `DEFAULT_PAGE_LIMIT` and
  `MAX_PAGE_LIMIT`. A third public constant added beside them and left out would make the list a
  thing nobody maintains — and `test_management_routes.py` imports the new constant by name.
- **Fix:** `"MAX_RETENTION_DAYS"` added, in the list's existing alphabetical position.

**5. [Rule 2 — an assertion that could not fail] the fail-open half of the no-figure test**

- **Found during:** Task 1.
- **Issue:** the plan says to keep the no-figure assertion under all three branches *"including
  failed-open"*. The file's existing fail-open provocation is `_ExplodingSessionmaker`, which raises
  before a session is ever opened — so no spend, limit or currency value was ever in the function's
  scope, and asserting their absence would have asserted nothing.
- **Fix:** the no-figure test's fail-open case is the **currency mismatch** on a third workspace,
  where `CEILING_READ` has returned and both the figures and both currency codes are live when
  `_UnevaluableCeilingError` is raised. `"VND"` was added to `FORBIDDEN_STRINGS` with the reason at
  the constant, and the test asserts a `call_ledger.ceiling_failed_open` record was actually captured
  so its own half cannot go vacuous.

---

**Total deviations:** 1 declared drift + 2 criterion readings + 2 auto-fixed (2 × Rule 2). **No
architectural change:** no new table, no migration, no new library, no new database routine, no new
role, no forbidden edge, no new `ErrorCode` member, and **no fifth `SECURITY DEFINER` function**. No
test was weakened, skipped, xfailed or deleted, and no threshold was raised.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (whole suite) | **337 passed, 1 warning in 181.28s** (326 at the 03-02 baseline) |
| `uv run ruff check src/ tests/ alembic/` | **All checks passed!** |
| Task 1 `<verify>`: `uv run pytest tests/integration/test_ceiling_refuses_evals_only.py -q` | **14 passed, 1 warning in 12.85s** |
| Task 2 `<verify>`: `uv run pytest tests/unit/test_retention_days_bound.py tests/integration/test_management_routes.py -q` | **40 passed, 1 warning in 26.26s** |
| `git status --porcelain docs/modules docs/architecture docs/adr` | no output |
| `grep -rn "ceiling_failed_open_total" src/ --include=*.py` | 2 lines, both inside the single retirement comment in `observability.py`; the `Counter` is gone |
| `grep -rn '"allowed"\|"refused"\|"failed_open"' src/ --include=*.py` | each literal exactly once, at its `CeilingCheckResult` member |
| `grep -rn "ArithmeticError" src/prope/call_ledger/drain.py` | no output, exit 1 |
| `git diff src/prope/call_ledger/drain.py` | empty — no `ArithmeticError` branch, `PERMANENT` default untouched |
| `git diff` inside `class ErrorCode` | empty — no member added |
| `timedelta.max.days` on this interpreter | `999999999`; `timedelta(days=10**9)` raises `OverflowError`; `issubclass(OverflowError, ArithmeticError)` is `True` |
| Negative control: `refused` relabelled `allowed` | **2 failed, 12 passed** — reverted |
| Negative control: `le=` removed from the field | **2 failed, 5 deselected** — reverted |
| `uv run ruff format --check` | **not run — not a gate.** Broken Window #1, unsatisfiable repo-wide |

**Literal tail of the final full-suite run:**

```
337 passed, 1 warning in 181.28s (0:03:01)
```

**Literal output of the lint gate:**

```
All checks passed!
```

## Human Verification Required

Two items, both of them the plan's own `<human-check>`s.

> **1.** ROADMAP SC3's words are *"increments the failed-open counter"*. This plan ships that as
> `prope_call_ledger_ceiling_check_total{result="failed_open"}` — the metric the lock file declares —
> and **retires** Phase 2's `prope_call_ledger_ceiling_failed_open_total`. Confirm that reading, so
> the verifier does not score SC3 against a constant that no longer exists.

> **2.** `MAX_RETENTION_DAYS = 3650` is a product-visible limit: no workspace can set a retention
> window longer than ten years through the API. Confirm the number, or name the one that replaces it.
> (Already `deferred-items.md` Part 1 item 4.)

## Flagged Assumptions Carried to Verification

The plan's flagged-assumptions block says no deterministic edge probe exists in this environment and
that both requirements' boundary conditions are an **agent enumeration, labelled as one**. All of
them are now asserted, which is evidence about the enumeration rather than about the probe:

| Enumerated boundary | Asserted by |
|---|---|
| no ceiling row | `test_a_workspace_with_no_ceiling_row_is_allowed` |
| a disabled ceiling row | `test_a_disabled_ceiling_allows_however_far_over_the_spend_is` |
| a ceiling with no monthly figure this month | `test_an_enabled_ceiling_with_no_priced_spend_this_month_is_allowed` |
| spend exactly equal to the limit | `test_spend_exactly_at_the_limit_refuses` |
| a currency mismatch between ceiling and spend | `test_a_ceiling_and_a_spend_in_different_currencies_fail_open` |
| an aggregate read that raises | `test_an_unevaluable_check_allows_and_counts_and_does_not_raise` |
| a month boundary in a non-UTC offset | `test_the_ceiling_reads_the_same_month_write_records_files_into` (pre-existing, still green) |
| CR-01's boundary pair | `test_the_largest_accepted_value_validates`, `test_one_day_past_the_bound_is_refused_by_name` |
| CR-01's overflow value | `test_the_overflow_this_bound_exists_to_prevent_is_unreachable_through_the_schema` |
| CR-01's zero and negative | `test_a_non_positive_window_is_still_accepted_by_the_model[0]` / `[-1]` |

One case the enumeration did not name was found while writing: a ceiling row whose `monthly_limit` is
NULL. It shares the first `allowed` branch with "no row" and "disabled", and is covered by the same
assertion.

## Known Stubs

None. Every symbol this plan created is driven by a test in this plan.

**`ceiling_check_total` is observable from tests and from nowhere else when this plan lands.** Plan
03-04 owns the `/metrics` route; until it runs, no scraper reaches this counter, and even afterwards
`ceiling_check_total` is one of the metrics `OQ-026` names as living only in a registry `app` does not
serve from — `check_spend_ceiling` is called by evaluation, which arrives in Phases 16–18. That gap is
03-04's to raise and is not narrowed here.

## Notes for the next plans

- **Plan 03-04's rules file must name `prope_call_ledger_ceiling_check_total`.** There is no
  `ceiling_failed_open_total` to write a rule against, and a rule referencing it would parse fine and
  alert never — which is exactly what D-44's registry-parsing test exists to catch.
- **The `result` label values are `CeilingCheckResult` members, not literals.** A rules file, a
  dashboard or a later increment site should import the enum rather than spell the value, and
  `test_the_result_vocabulary_is_the_three_values_the_lock_file_declares` pins the spelling because a
  rules file matches on the string.
- **`ceiling_check_total` moves only when `check_spend_ceiling` is called, and nothing calls it in
  production yet.** Its increment sites are proved from call-ledger's own tests, which is the posture
  Phases 1 and 2 established for every seam whose caller arrives in Phase 16.
- **`RetentionSet` now carries `Field(le=...)`, which changes the assembled OpenAPI schema for
  `PUT /api/v1/workspaces/{id}/retention`.** `tests/architecture/test_route_table.py`'s OpenAPI walk
  passes unchanged, but any later plan asserting on that schema's shape should know the constraint is
  there.
- **`schemas.py` maintains an explicit `__all__`.** A public constant added to that file and left out
  of it is a list that has stopped being maintained.
- **The A-056 no-figure assertion is now a three-branch test with `VND` in its forbidden set.** A
  later plan seeding a VND ceiling anywhere in that file will need to check it does not trip its own
  search.

## Self-Check: PASSED

- `tests/unit/test_retention_days_bound.py` exists; all six modified files carry this plan's changes.
- `src/prope/observability.py` defines `ceiling_check_total` with `labelnames=("result",)` and no
  longer defines `ceiling_failed_open_total`.
- `src/prope/call_ledger/seams.py` defines `CeilingCheckResult` with exactly three members, imports
  `ceiling_check_total`, and increments it at all four `return` sites plus the `except` handler.
- `CeilingDecision`'s field list is still exactly `["allowed", "reason"]`.
- `src/prope/call_ledger/schemas.py` defines `MAX_RETENTION_DAYS = 3650`, `retention_days` carries
  `le=MAX_RETENTION_DAYS` rather than a literal, and the lower-bound paragraph is unchanged in
  substance.
- `src/prope/call_ledger/drain.py` is untouched by this plan and contains no `ArithmeticError`.
- `uv run pytest -q` → **337 passed**. `uv run ruff check src/ tests/ alembic/` → clean.
- No file under `docs/modules`, `docs/architecture` or `docs/adr` was modified, no `OQ-NNN` was
  claimed, and no tracked file was deleted.

---
*Phase: 03-durability-idempotency-and-no-read-path*
*Completed: 2026-08-11*

# Phase 4 — adversarial spec-fidelity critique of the plan set

**Written:** 2026-08-10 · **Role:** critic-spec · **Scope:** `04-CONTEXT.md`, `04-01`…`04-04-PLAN.md`,
`COVERAGE.md`, `deferred-items.md`, checked against `docs/modules/property-history.lock.yml`,
`docs/architecture/interfaces.md`, ADR-0023/0024/0025/0027/0035/0037/0038/0045/0054,
`.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/research/PITFALLS.md`,
`.planning/BSP-LINK.md`, `.claude/CLAUDE.md`.

> **No detector was run.** `api-coverage.cjs`, the edge probe and the assumption-delta detector do not
> exist in this environment (ORCHESTRATION §0). Every claim below is an agent judgement made by reading
> the named files, and every file:line reference was opened, not inferred.

---

## What is right, so the findings below are read against it

These were checked and are correct; they are stated once and not re-litigated.

- **Requirement ownership is exact.** PH-02 → `04-01`, PH-05 → `04-02`, PH-04 → `04-03`, each in exactly
  one plan's `requirements:` field; `04-04` carries none and says why. Every ROADMAP success criterion has
  exactly one owner (SC1 → 04-01 Task 3, SC2 → 04-03 Task 1, SC3 → 04-02 Task 3).
- **The 31-name derivation is correct.** I re-derived it independently from the five lock files'
  `outputs[].what` blocks: prompt-registry 5 (`prompt-registry.lock.yml:90`), release-control 8
  (`release-control.lock.yml:102-103`), evaluation 4 (`evaluation.lock.yml:96`), provider-access 4
  (`provider-access.lock.yml:93`), access-control 10 including `user_tombstoned`
  (`access-control.lock.yml:110-111`). Union = 31, no adjustment, no rounding. D-60's table matches
  name-for-name.
- **OQ-027 is a real conflict and is named precisely.** ADR-0024's title, Context table and Consequences
  say 30; its Decision block (`action one of 31 registered names`) says 31. Confirmed by reading the ADR.
- **OQ-031 is a real conflict and both halves check out.** ADR-0045:46-51 does contain
  `'history.history_action_registry': "30 seeded actions…"`, and `tests/architecture/test_tenant_coverage.py:118-121`
  does `continue` with no assertion where the ADR's pseudocode writes `assert rls_state_matches_declaration(table)`.
- **The four non-negotiables are intact.** Nothing auto-releases, nothing weakens the Approved-only
  constraint, no permission is merged, and prompts-private-by-default is untouched. History rows are
  never deletable by `prope_app` **because of an absent grant**, which is the non-negotiable in its
  strongest form.
- **No fifth `SECURITY DEFINER` is proposed anywhere.** 04-01's prohibition block forbids one, and D-49's
  parameterisation extends `test_the_ledger_schema_contains_no_security_definer_function` to `history` —
  correctly labelled in COVERAGE §1 as delivering the `history` half of an access-control PITFALLS §1
  item **without claiming that criterion**.
- **PITFALLS gaps 1 and 2 are handled honestly.** property-history appears in neither table; I checked
  both. `04-CONTEXT.md` records the absence rather than inventing a restatement, and no plan asserts a
  lock file's literal AC text where a restatement was owed.
- **Forbidden edges hold.** `src/prope/property_history/` imports no other module, imports no FastAPI,
  and touches neither `app.py` nor `worker.py`. `dependencies: []`, `outputs: []`, `apis.consumes: []`
  survive intact. No plan writes a table outside `data.owns[]`.
- **`prope_report` is safe.** The plan's cross-workspace argument for `report_select=True` depends on
  `prope_report` not being policy-bound; `alembic/versions/0001_roles_and_schemas.py:47` creates it
  `LOGIN BYPASSRLS` and `enable_tenant_rls` scopes the policy `FOR ALL TO prope_app`, so ADR-0037's read
  actually works. This was checked because the plan asserts it without proving it.
- **D-57's composite key is defensible.** A-122 forbids a foreign key on `target_id`, not on `action`; the
  key is intra-schema; its target is global and byte-identical per workspace, so
  `test_no_foreign_key_leaves_the_ledger_schema`'s covert-channel reason genuinely does not transfer. The
  lock's *"constrained against the registry at append"* is compatible with also constraining it at the
  engine. **No conflict with a literal spec token, so no OQ is owed here** — which is what makes finding
  2 below different in kind rather than in degree.

---

## Findings

### 1. `test_a_gap_in_seq_is_not_a_missing_event` asserts a gap the implementation cannot produce — and the same false claim is written into the shipped migration docstring

**Severity: blocker**
**Where:** `04-03-PLAN.md` § Task 1, behaviour bullet 5, action item 3, and acceptance criterion
*"a refused append between two successful ones leaves a gap greater than one"*; `04-03-PLAN.md`
`must_haves.truths` line 7; `04-03-PLAN.md` § Objective, *"Three: the two inferences nothing may make"*;
and **`04-01-PLAN.md` § Task 1**, the comment ordered at the `seq` column:
*"a refused append consumes a value and never returns it, and PH-05's own criterion guarantees refused
appends, which makes gaps a **normal product of this phase's third requirement**"*.

**Authority it contradicts:** `04-02-PLAN.md`'s own contract for the same code —
`must_haves.truths`: *"An event whose action is not in the registry raises `HistoryAppendRejected` with
reason `unknown_action`, **before any SQL is issued**"*, and `<behavior>`: *"An action absent from the
registry raises … before any SQL is issued"*. Task 3's code sketch confirms it: `check_event` runs its
three `if`s and raises; `session.execute(INSERT_HISTORY_EVENT, …)` is never reached.

**Why it matters.** PostgreSQL's *"`nextval` and `setval` calls are never rolled back"* only produces a
gap when an `INSERT` actually executed and was then rolled back. A validator refusal in this design
issues no statement, so `nextval` is never called and no sequence value is consumed. Test 3 as specified
writes a valid event, refuses one **in its own transaction**, then writes a second valid event: the two
survivors take consecutive values and `second.seq - first.seq` is **1**, not `> 1`. The test is red on
arrival, which ORCHESTRATION §9 forbids (*"a red test is never 'expected'"*), and the likely executor
repair — relaxing the assertion to `>= 1` — deletes the only thing the test was for. Worse, the
identical false claim is ordered into the **migration docstring** (04-01), the most-read artifact this
phase ships, where Phase 6's AC-10 (*events are never deleted*) reader will take it as fact.

**Fix.** Two edits, both small.
(a) In 04-03 Task 1 test 3, provoke a refusal that **reaches the engine**: either a hand-written `INSERT`
violating `fk_history_event_action` inside its own transaction, or a *valid* `record_event` on a
caller-opened transaction that is then abandoned (04-02 Task 3 test 2 already builds exactly that
scenario). Both consume a sequence value and leave a real gap.
(b) Restate the claim wherever it appears (04-01's `seq` comment, 04-03's objective and truths) as: *a
rolled-back **INSERT** consumes a sequence value and never returns it; a validation refusal raises before
any statement is issued and consumes nothing. Both are normal; neither is evidence an event was deleted.*
That is the sentence Phase 6 needs, and it is the one that is true.

---

### 2. D-53's deviation from the lock's `bigserial` is withheld from OQ on a justification that plan 04-03 exists to disprove

**Severity: major**
**Where:** `04-CONTEXT.md` § D-53 (*"No OQ is raised for a strengthening that changes neither the column
type (`bigint` either way) nor the observable behaviour"*), repeated verbatim as the ground for withholding
in `deferred-items.md` §2 row 2, and ordered into the revision docstring by `04-01-PLAN.md` § Task 1,
docstring item 2.

**Authority:** `docs/modules/property-history.lock.yml` `data.owns` →
*"`seq` — **bigserial**, monotonic, and the ONLY sort key"*, and `docs/adr/0024-…` Decision block →
`seq  bigserial, monotonic — the ONLY sort key (A-125)`. ORCHESTRATION §5 / BSP-LINK "Out of bounds":
*"If one of those turns out to be necessary, that is real information — the spec is wrong. Stop, write an
`OQ-NNN` naming the exact lock file field and the conflict."* Phase 2's precedent is four such files,
OQ-018…OQ-021, carried in ORCHESTRATION §4 as *"four declared spec deviations raised, not absorbed"*.

**Why it matters.** The stated ground is false, and the phase's own plan set proves it false:
`04-03-PLAN.md` Task 2 test 1 asserts that *"an `INSERT` naming `seq` with a value, attempted as
`prope_app`, raises `DBAPIError` whose message contains `generated always`"*. Under the lock's
`bigserial` that statement **succeeds silently**. That is a behavioural difference on the column the
module's second success criterion rests on — the deviation is exactly the kind Phase 2 raised, and it is
being absorbed on a claim that is contradicted three plans over. The deviation itself is right; the
paperwork is what is wrong, and the paperwork is the only thing that puts the choice in front of a human
who could say *no, keep `bigserial` and enforce it in the writer*. Contrast D-50, which is genuinely a
spelling difference with a byte-identical end state, and D-57, which adds no conflict with a literal spec
token — both are correctly left un-OQ'd.

**Fix.** Raise one OQ naming `docs/modules/property-history.lock.yml` `data.owns → history_event → seq`
and `docs/adr/0024-…` Decision block, stating the conflict as *"the spec names a default-backed sequence;
the build ships `GENERATED ALWAYS`, which refuses a caller-supplied value — a strengthening with an
observable behavioural difference, asserted in `tests/security/test_history_seq_cannot_be_supplied.py`"*.
Cite it in D-53, in `deferred-items.md` §2 row 2 and in the revision docstring in place of the current
"no OQ" sentence. **Note for the orchestrator: this phase's allocated OQ range OQ-027…OQ-031 is fully
consumed**, so this file needs an id allocated outside the phase's range.

---

### 3. The `detail_keys` derivation misses `evaluation.lock.yml`, which declares payload keys for four of the twenty-eight actions seeded empty

**Severity: minor**
**Where:** `04-CONTEXT.md` § D-61 (*"Three of thirty-one actions have declared keys — `revision_released`
…, `role_assigned` …, and `user_tombstoned` (deliberately empty). The other twenty-eight belong to
modules that will not exist for another six to eighteen phases"*), and `04-01-PLAN.md` § Task 1, the seed
table (all four `eval_*` rows carry `{}`) plus the seed-comment instruction *"`detail_keys` is declared
for three of thirty-one and the other twenty-eight are seeded empty"*.

**Authority:** `docs/modules/evaluation.lock.yml:94-97` — *"to: property-history … what:
`eval_suite_updated`, `eval_run_started`, `eval_run_completed`, `eval_run_interrupted`, **with the
prompt_id, version_id, suite_version, and actor** (A-014)."* `prompt_id` maps to `scope_prompt_id` and
`actor` to `actor_id`, but `version_id` and `suite_version` are columns `history_event` does not have —
so they are `details` keys, declared, today, in a lock file that exists.

**Why it matters.** It is not a Phase 4 or Phase 5 failure — AC-6 asserts action names only, so nothing
goes red. It fails twelve phases later: Phase 16 writes `eval_run_started` with
`details={"version_id": …}` and the append is refused with `unknown_detail_key`, which is precisely the
lock's *"the realistic cause is a rename shipping half-applied"* failure mode arriving from the seed
instead. And the derivation is the artifact this phase owes Phase 5 as a written baseline, so an
inaccuracy in it is inherited rather than corrected.

**Fix.** Either seed `version_id` and `suite_version` for the four `eval_*` actions with a comment citing
`evaluation.lock.yml:96`, or keep the strict empty seed and correct the sentence to *"declared keys exist
in a lock file for **seven** of thirty-one actions; four of them (evaluation's) are seeded empty
deliberately, because the module that will write them is Phase 16 and it should register them with its
own test"* — and add that specific handover to `OQ-029`, which today carries only the generic obligation.
Either way the count "three of thirty-one" must not ship as written.

---

### 4. `HistoryEventDraft` makes `id` caller-supplied; INT-006's registered envelope does not carry `id`

**Severity: minor**
**Where:** `04-02-PLAN.md` § Task 2, `HistoryEventDraft` — *"and `id: str = field(default_factory=…)`
last"* — and § Task 3's `INSERT_HISTORY_EVENT`, which binds `:id` from the draft. Also
`04-02-PLAN.md` acceptance criterion *"`HistoryEventDraft` declares eleven fields"*, against
`04-CONTEXT.md` § Canonical refs, which describes INT-006 as *"the envelope's **ten** caller-carried
fields"*.

**Authority:** `docs/architecture/interfaces.md` INT-006 → *"**Envelope carries**: `workspace_id`,
`actor_type`, `actor_id`, `action`, `target_type`, `target_id`, `scope_prompt_id`, `reason`, `details`,
`occurred_at`. `seq` is database-assigned."* Ten fields. `id` is not among them and — unlike `seq` — is
not called out as database-assigned either, because A-045/ADR-0003 make it the *provider's* to mint.

**Why it matters.** An undeclared widening of a registered seam. A caller can supply an `id`, which means
a caller can supply a non-`hev_` id, a duplicate (a bare PK violation instead of a named refusal), or an
id that sorts wrongly against a ULID assumption a later phase makes. Phase 5 inherits the widened draft
as the input type it wraps as `append()`, so the deviation propagates into INT-006's actual
implementation without ever having been declared. CONTEXT left *"the `id` generation site"* open under
Claude's Discretion; the plan resolved *where* it is minted but not *whether the caller may override it*,
which is the half INT-006 answers.

**Fix.** Mint the id inside `record_event` and drop `id` from `HistoryEventDraft` (returning it, which
INT-006 already implies by making it the value that is logged); or keep the field and declare the
deviation explicitly in `deferred-items.md` §3 naming `interfaces.md` INT-006 *Envelope carries*. Do not
leave it as an eleventh field nobody said was an eleventh field.

---

### 5. The `OVERRIDING SYSTEM VALUE` boundary note asserts the opposite of what the engine does

**Severity: minor**
**Where:** `04-03-PLAN.md` § Task 2 test 3 — *"a supplied `seq` above the sequence's current value does
**not** advance the sequence, so the next engine-assigned value collides with it and
`uq_history_event_seq` refuses that insert — which means the escape hatch does not silently corrupt the
order so much as **break the next append, loudly**"* — plus the acceptance criterion demanding *"one
determinate outcome, not 'either of two'"*.

**Authority:** A-125 / ADR-0024 — `seq` is the only sort key and *"two events written in one transaction
have a defined order"*; the lock's failure-mode row on rendering order.

**Why it matters.** The determinate outcome the executor will actually observe is the *first* of the two
the plan offers: the next append gets the next sequence value, which is **lower** than the supplied one,
so it succeeds and sorts **before** an event that was written earlier. The order is silently wrong from
that moment, and it stays silently wrong until the sequence climbs to the supplied value — a collision
that may be years away at *"< 500 events per prompt property per year"*. So the sentence the plan orders
written into the file's docstring is not merely imprecise, it is reassuring in the direction of the real
hazard, and it will be read by whoever inherits this boundary.

**Fix.** Replace the sentence with what the assertion will prove: *"a supplied `seq` does not advance the
sequence, so the next engine-assigned value is lower than the supplied one and orders before it. The
escape hatch corrupts the order silently, and it stays silent until the sequence reaches the supplied
value. That is why the source gate in `tests/architecture/test_no_overriding_system_value.py` exists and
why the engine assertion alone is not the control."*

---

### 6. `COVERAGE.md` says pydantic becomes used; `04-02` says it deliberately does not

**Severity: minor**
**Where:** `COVERAGE.md` § 2 — *"Two libraries move from *pinned and unused* to *pinned and used* —
`python-ulid==4.0.1` for the `hev_` prefix and **`pydantic==2.13.4` for the `details` payload's shape**"*
— against `deferred-items.md` §3, *"`pydantic`'s scope is narrowed … The allow-list check is
`set(details) - registered_keys`, a set difference"*, and `04-02-PLAN.md` § Task 2, where
`HistoryEventDraft` is a frozen `dataclass` and no pydantic model is declared anywhere.

**Authority:** `docs/modules/property-history.lock.yml` `libraries_frameworks` — *"pydantic v2 —
validates the `details` payload against the per-action key allow-list at append time (A-124)"*.

**Why it matters.** The deviation from the lock is fine and well argued; the phase's own coverage artifact
denies that the deviation exists. A verifier reading COVERAGE will look for a pydantic model, not find
one, and either flag a phantom gap or — worse — conclude the coverage table is decorative. On this module
the coverage table is the only enumeration of what the phase touches.

**Fix.** One line in `COVERAGE.md` §2: `python-ulid` moves to *used*; **pydantic does not**, with a
pointer to `deferred-items.md` §3 and to the lock field it deviates from.

---

### 7. `record_event` ends Phase 4 as an importable module function named in no `apis.exposes` row and no INT row

**Severity: minor**
**Where:** `04-CONTEXT.md` § D-64, `04-02-PLAN.md` § Objective and Task 3, `deferred-items.md` §2 row 6.

**Authority:** `docs/modules/property-history.lock.yml` `apis.exposes` names exactly three internal
functions — `append(event)`, `read(scope, cursor, limit)`, `registered_actions()`. BSP-LINK "Out of
bounds": *"Do not expose an API or event outside its `apis.exposes[]`."* `.planning/ROADMAP.md` Phase 5
goal names `append()`; `.planning/REQUIREMENTS.md` routes PH-05 to Phase 4.

**Why it matters — and why it is only minor.** The tension is inside the authorities themselves: ROADMAP
puts `append()` in Phase 5 and PH-05 in Phase 4, and PH-05 is not observable without a write path, so
*something* has to give. D-64 gives the right thing, declares it in three places, and routes it to two
`<human-check>` items. The residual is that no artifact names this as an **authority conflict** — it
reads as a planner's convenience — and the executor of Phase 5 will find a function whose name it must
retire rather than a seam it may build beside.

**Fix.** No plan change. Add one line to `deferred-items.md` §5 addressed to **Phase 5**: *"`record_event`
is a rename target, not a second seam. INT-006's `append()` replaces or wraps it and `record_event` must
not survive as a public name past Phase 5."* Optionally record the ROADMAP-internal tension in
`.planning/ORCHESTRATION-DECISIONS.md` alongside the adoption, so the human adjudicating sees it is a
spec tension and not a preference.

---

### 8. `04-04`'s `files_modified` omits `.planning/WINDOWS.md`, which the same plan instructs its executor to write

**Severity: minor**
**Where:** `04-04-PLAN.md` frontmatter `files_modified` (two test files), against its own § *Artifacts
this plan produces* — *"**Appended to `.planning/WINDOWS.md` by the executor**: the `request_id`
allow-list omission … in both the table and the JSON block with `open_count` corrected"* — and its
verification line *"this plan writes only under `tests/` **and appends to `.planning/WINDOWS.md`**"*.

**Authority:** ORCHESTRATION §7 — *"Parallel within a phase: plans in the same declared `wave:` whose
`files_modified` are provably disjoint. The planner declares the waves; the orchestrator enforces
disjointness before fanning out."*

**Why it matters.** `04-03` and `04-04` are both `wave: 3`. The orchestrator's disjointness check reads
`files_modified` and nothing else, so a file written by a wave-3 plan but absent from its declaration is
invisible to the one mechanism that prevents concurrent writes. It happens to be harmless here (04-03
does not touch WINDOWS.md), which is exactly why it will be repeated.

**Fix.** Add `.planning/WINDOWS.md` to `04-04`'s `files_modified`.

---

### 9. The stated reason for `tests/property_history/`'s placement is defeated by the same task's import instruction

**Severity: minor**
**Where:** `04-01-PLAN.md` § Task 2 — *"The rejected alternative is `tests/unit/__init__.py`, which
already imports `prope.call_ledger.domain` and `prope.call_ledger.seams` at module scope — adding history
factories there would make one helper module import two bounded contexts"* — immediately followed by
*"**Reuse rather than restate.** Import `WORKSPACE_A`, `WORKSPACE_B`, `WORKSPACE_C`, `DAY_1` and `day`
**from `tests.unit`**"*.

**Authority:** the module's own defining property, `docs/modules/property-history.lock.yml`
`dependencies: []` / `apis.consumes: []`, which the plan invokes as the reason for the separation.

**Why it matters.** Importing `tests.unit` executes its module scope, so `tests/property_history/`
transitively imports both call-ledger modules anyway. The placement is probably still right — a
per-subject package mirroring `tests/broker/` — but the argument as written is false, and a false
argument in a docstring is worse than no argument, because the next person reasons from it. It also
matters slightly more here than elsewhere: this is the one module in Prope whose selling point is that it
imports nothing.

**Fix.** Either keep the import and restate the reason honestly (*"a per-subject package mirroring
`tests/broker/`; the shared calendar constants still come from `tests.unit`, which is a test-rig
dependency and not a module edge"*), or re-home `WORKSPACE_A`/`DAY_1`/`day` into a neutral
`tests/fixtures.py` — a bigger change than this phase should make, so the first option is the one to take.

---

## Checks that produced nothing, listed so the absence is evidence

- No plan writes outside `data.owns[]`, adds a route, adds a broker queue, adds a dependency, adds a
  trigger, adds a native enum, adds a `SECURITY DEFINER`, or edits anything under `docs/` other than
  creating `OQ-027`…`OQ-031`.
- No plan asserts against a lock file's literal AC text where PITFALLS §1/§2 owed a restatement;
  property-history appears in neither table, verified line by line.
- AC-2, AC-4 and AC-5 are asserted in the restated-but-faithful form, and each carries a positive control
  that makes the test capable of failing: the visible-row control inside the attempting transaction
  (AC-2), the distinct-`occurred_at`-count control (AC-4), and the valid-event-written-first control
  (AC-5). None of the three is a test that cannot fail.
- The UNCONFIRMED adoptions were re-examined against their rejected alternatives. Seven of eight are the
  better option rather than the more convenient one — in particular the `LOGGABLE_FIELDS` resolution
  (04-02 Task 1), where the *more convenient* answer was to leave the set alone and the adopted answer is
  the one that makes the prohibition an absence. The eighth, D-53, is also the better option; only its
  paperwork is wrong (finding 2).

---

VERDICT: 1 blocker / 1 major / 7 minor

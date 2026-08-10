# Phase 4 — Deferred items

Out-of-scope discoveries found while planning, the decisions adopted without confirmation under
`mode: yolo`, and the open-question ids this phase consumed. **Logged, not fixed.** The executor and the
reviewer append to this file; the planner seeded it.

---

## 1. Open questions — the allocation, and what each one says

Phase 4's allocated range is **OQ-027 … OQ-031** and **all five are consumed.** No id outside the range
was touched; `OQ-022 … OQ-026` belong to Phase 3.

| id | Raised by | Severity | Conflict, in one line |
|---|---|---|---|
| **OQ-027** | `04-CONTEXT.md` (D-60) | medium | The vocabulary count is **30 in six places and 31 in five**, twice inside the same file. ADR-0024's title, Context table and Consequences say 30; its line 53 says 31. `interfaces.md` says 31 in INT-006's header and INT-008's row and 30 in INT-006's validation bullet. A-120 says 31 in its Statement and 30 in its Rationale. **31 is adopted** — the lock file, ADR-0038, ADR-0054, `tech_stack.md` and the derivation from the five `outputs` blocks all agree |
| **OQ-028** | `04-CONTEXT.md` (D-61) | low | **Four of the 31 names do not satisfy A-120's own `<target_type>_<past participle>` rule** against their real target: `retired` (no target type at all), `owner_changed` and `access_level_changed` (a field, not a subject), and `access_granted`/`access_revoked` (whose subject is the `prompt_grant` row). The migration seeds the names the lock files literally contain, because AC-6 is an asserted equality and A-120 is prose |
| **OQ-029** | `04-CONTEXT.md` (D-61) | medium | `target_type` is declared a *closed enumeration* and is **enumerated nowhere** — the only member stated in `docs/` is `target_type = user` (A-151). Thirteen values are derived and seeded. `detail_keys` is declared for **3 of 31** actions and the other 28 belong to modules six to eighteen phases away. Also carries the A-119 *"six different `target_type`s"* count that derives as **seven**, and the unowned obligation that each writing module later registers its own keys |
| **OQ-030** | `04-PATTERNS.md` | medium | The lock declares `prope_property_history_rows_total` **labelled by `workspace_id`**, and `tests/broker/test_publish_confirm_failures.py:239-250` already asserts that no `prope_*` metric may carry one. **Blocks Phase 6, not Phase 4** — this phase's only metric is labelled by a closed three-member `reason` set |
| **OQ-031** | **this planner** (plan 04-01, Task 1) | low | `docs/adr/0045-…:46-51` already contains the `GLOBAL_TABLES` entry plan 04-01 writes, verbatim as `'history.history_action_registry': "30 seeded actions, immutable, ADR-0024 and ADR-0038"`. **Two conflicts in one line.** It is a *seventh* stale-count site for OQ-027 — and the only one whose text this phase was about to copy into a security-relevant file, which is why the reason string in `test_tenant_coverage.py` deliberately carries no number. And the ADR's own pseudocode writes `assert rls_state_matches_declaration(table); continue` where the implemented walk at `test_tenant_coverage.py:120-121` writes `continue` with **no assertion at all**, so a `GLOBAL_TABLES` exemption currently buys no check whatsoever |

**Why OQ-031 rather than an edit to OQ-027.** `04-RESEARCH.md` suggested appending the ADR-0045 row to
OQ-027's table on the grounds that OQ-027 is this phase's own artifact. `.planning/ORCHESTRATION.md` §1
permits **creating** an `OQ-NNN` file and nothing else under `docs/`, and reading that strictly is the
cheaper mistake. A new id also keeps the two questions separable: a resolver can fix a count without
taking a position on whether the coverage walk should assert against its exemptions.

### ESCALATED TO THE ORCHESTRATOR — one OQ is owed and this phase cannot allocate its id

Added at plan-critique resolution, on a finding this phase's planner got wrong and did not catch.

| Owed OQ | Against | Conflict, stated as the file would state it |
|---|---|---|
| **id unallocated — orchestrator to assign** | `docs/modules/property-history.lock.yml` `data.owns → history_event → seq` (*"`seq` — **bigserial**, monotonic, and the ONLY sort key"*) and `docs/adr/0024-one-event-schema-with-a-registered-payload.md`'s Decision block (`seq  bigserial, monotonic — the ONLY sort key (A-125)`) | The spec names a default-backed sequence; the build ships `GENERATED ALWAYS AS IDENTITY`, which **refuses a caller-supplied value**. This is a strengthening with an **observable behavioural difference**, not a spelling difference: under `bigserial`, `INSERT INTO history.history_event (seq, …) VALUES (:seq, …)` as `prope_app` succeeds silently; under `GENERATED ALWAYS` the engine raises. `tests/security/test_history_seq_cannot_be_supplied.py` (plan 04-03 Task 2 test 1) asserts the raise, which is what makes the difference observable rather than theoretical. `blocks_build: false` — the build ships either way, and the decision is the better of the two options; what is owed is the record that lets a human say *no, keep `bigserial` and enforce it in the writer* |

**Why it is escalated rather than raised here.** `04-CONTEXT.md`'s D-53 originally withheld the OQ on
the ground that the deviation *"changes neither the column type (`bigint` either way) nor the observable
behaviour"*. The second half is false and the phase's own plan set proves it false three plans over.
D-53 has been corrected in place and plan 04-01's revision docstring now records the deviation, the
behavioural difference and the test that proves it. **The id is the only thing missing**, and
`OQ-027 … OQ-031` are consumed while `OQ-022 … OQ-026` belong to Phase 3 — taking one from another
phase's range is the failure the range allocation exists to prevent. The orchestrator allocates an id
outside both ranges and the file is written against the text in the table above.

---

## 2. Adopted without confirmation — the adjudication list

Eight decisions were made on the user's behalf because `mode: yolo` is set and this run does not stop at
blocking checkpoints (`.planning/ORCHESTRATION.md` §6). **Every row belongs in `04-UAT.md` as a numbered
human-verification item and in `.planning/ORCHESTRATION-DECISIONS.md` as one row.**

Six were adopted in `04-DISCUSSION-LOG.md` and are carried into the plans rather than re-opened — the
posture plan 02-04 took for D-18 and D-20, on the grounds that a checkpoint re-asking a settled question
is not a checkpoint. Two are the planner's own and carry full `checkpoint:decision` blocks.

| # | Decision | Plan | What was adopted, and what was rejected | Reversibility |
|---|---|---|---|---|
| 1 | **D-50** | 04-01 | `grant_table`'s **positive form** — `REVOKE ALL FROM PUBLIC` then `GRANT SELECT, INSERT` — instead of the lock file's literal `REVOKE UPDATE, DELETE ON history.history_event FROM prope_app`. Rejected: issuing the literal REVOKE as well (a no-op that reads in a diff as protection) and issuing it instead of the helper (`history_event` becomes the one table whose grants a reviewer cannot find by grepping `grant_table`). **No OQ raised** — a deviation in spelling with an identical end state, and the end state is what the test asserts | one-way in D-07's sense |
| 2 | **D-53** | 04-01 | `bigint GENERATED ALWAYS AS IDENTITY (CACHE 1)` where the lock says `bigserial`. Rejected: `bigserial` (a `DEFAULT`, and a default is only consulted when the caller omits the column, while `prope_app` holds `INSERT` by design) and `GENERATED BY DEFAULT` (behaves as `bigserial` while carrying the word "identity"). **CORRECTED at plan-critique resolution: an OQ IS owed and its id is escalated in §1 above.** The original ground — *"a strengthening that changes neither the column type nor the observable behaviour"* — is false in its second half: an `INSERT` naming `seq` succeeds under `bigserial` and is refused under `GENERATED ALWAYS`, which `tests/security/test_history_seq_cannot_be_supplied.py` asserts. The decision stands; the paperwork was wrong, and the paperwork is what puts it in front of a person | one-way once rows exist |
| 3 | **D-56** | 04-01 | `history.history_action_registry` carries **no `workspace_id`** and becomes the project's first `GLOBAL_TABLES` entry, with a reason string that deliberately contains no number. Rejected: a tenant-scoped registry (returns zero rows to `registered_actions()`'s only consumer, and AC-6 then compares two empty sets and passes forever) and a Python constant (ADR-0024 and D-57 both need a table) | costly |
| 4 | **D-57** | 04-01 | A **composite foreign key** `history_event (action, target_type) → history_action_registry (action, target_type)`, on a tenant-scoped table where Phase 1 refused foreign keys in `ledger`. The refusal reason does not transfer — this key's target is global and identical for every workspace, so the RI check leaks nothing. Rejected: `CHECK (action IN (…31…))`, no constraint at all, and a `BEFORE INSERT` trigger. **Cost recorded rather than measured**: thirty-one multixact-capable hot rows, an agent judgement from arithmetic against 200 appends/sec on one VM | cheap to drop, costly to add later |
| 5 | **D-61** | 04-01 | Seeding `retired`, `owner_changed` and `access_level_changed` under the names the lock files literally use — leaving A-120 false for four of thirty-one names — plus a **derived** thirteen-value `target_type` set and twenty-eight actions seeded with an **empty** `detail_keys`. Rejected: renaming on the way in, which would make Phase 5's AC-6 red. `OQ-028` and `OQ-029` are the record | one-way after the pilot |
| 6 | **D-64** | 04-02 | **The validating write path lands in Phase 4**, under the name `record_event`, which no downstream spec uses; Phase 5 renames or wraps it as INT-006's `append()`. Rejected: putting `append()` entirely in Phase 5, which makes this phase's third success criterion unprovable — forbidden by ORCHESTRATION §9. Requirement ownership is untouched | cheap |
| 7 | **`LOGGABLE_FIELDS` on `reason`** | **04-02, Task 1** | `reason` keeps call-ledger's meaning **exclusively**; property-history's classification token is renamed `rejection_reason`; the user-authored `reason` string gets **no allow-list name at all**, so the prohibition is an absence rather than a subtraction rule. The set grows 9 → 18 and the file's scope sentence is edited in the same change. Rejected: a per-module allow-list (ships two frozensets nobody reads unless the checker is built, and makes A-046 a property a module can forget to assert) and a floor-and-subtract rule (a deny-list wearing an allow-list's clothes, which that file's own docstring refuses) | costly — seven more modules inherit the shape |
| 8 | **A-046 enforcement scope** | **04-04, Task 1** | The **runtime marker assertion** here, over the paths this module exercises, plus the first read of `LOGGABLE_FIELDS` anywhere in the project. The **AST source gate is routed to Phase 6**, which owns AC-8. Rejected: building the gate now — it goes red on arrival against `src/prope/call_ledger/schemas.py:442`, forcing a third cross-phase edit no requirement in this phase asks for, and it cannot see dynamically-built log payloads | reversible — one file either way |

**None of the eight touches a §2 non-negotiable.** Rows 1, 2 and 4 all move toward a stronger
engine-enforced guarantee, which is the direction the non-negotiables point.

---

## 3. Declared deviations that are **not** raised as open questions

Recorded here so a reviewer finds them deliberately rather than by diff.

- **`pydantic`'s scope is narrowed.** The lock's `libraries_frameworks` says pydantic *"validates the
  `details` payload against the per-action key allow-list"* and concedes in the same field that it was
  *"chosen because it is already the baseline's validation library … not for a property specific to this
  module"*. The allow-list check is `set(details) - registered_keys`, a set difference; building
  thirty-one `create_model(..., extra="forbid")` models to express it would buy coercion nobody asked
  for and turn one clear refusal into a `ValidationError` that then has to be translated back into
  D-63's three-member vocabulary — adding a failure mode to the path whose whole point is that it has
  exactly three. **A deviation in mechanism with an identical end state**, riding D-50's footing.
- **AC-5's `test_ref` path moves.** The lock names
  `tests/unit/test_unregistered_detail_key_fails_the_transaction`; the transaction half lands in
  `tests/integration/`. "The caller's transaction rolls back with no partial state" is not observable
  without a database, and in this repository `tests/unit/` means pure Python. **Both halves of AC-5 are
  asserted**, which is more than the single named file would have delivered. A `test_ref` names a file,
  not a guarantee.
- **`HistoryEventDraft` carries an `id` field that INT-006's envelope does not name.**
  `docs/architecture/interfaces.md` INT-006's *Envelope carries* lists ten fields — `workspace_id`,
  `actor_type`, `actor_id`, `action`, `target_type`, `target_id`, `scope_prompt_id`, `reason`,
  `details`, `occurred_at` — and adds *"`seq` is database-assigned."* `id` is not among them and,
  unlike `seq`, is not declared database-assigned either, because A-045 / ADR-0003 make it the
  provider's to mint. Plan 04-02's draft carries it as an eleventh field with a `hev_`-prefixed default
  factory, so `record_event` can return a value the caller already holds, and `__post_init__` refuses
  an `id` without the prefix. **A widening of a registered seam, declared rather than raised**: the
  seam itself is Phase 5's — `record_event` is not `append()` and no spec names it — so Phase 5 is
  where the two must be reconciled, either by dropping the field and returning the minted id or by a
  spec change nobody has made. Recorded in §5 with Phase 5 named.
- **`tests/property_history/` is a helper-only package for two phases.** No test module lives in it in
  Phase 4; Phase 5's contract tests and Phase 6's chaos tests are where that changes. **The stated
  reason for the placement was corrected at plan-critique resolution.** The original argument — that
  `tests/unit/__init__.py` was rejected *because* it imports two call-ledger modules at module scope —
  is false, because `tests/property_history/__init__.py` imports `WORKSPACE_A` / `DAY_1` / `day` **from
  `tests.unit`** and so pulls the same two modules in transitively. The real reason is precedent: a
  per-subject package, mirroring `tests/broker/`. The shared calendar constants remain a **test-rig
  dependency, not a module edge** — `dependencies: []` is a statement about `src/prope/`. Re-homing the
  four constants into a neutral `tests/fixtures.py` would make the original argument true and is a
  repo-wide refactor no requirement asks for; **not done, and available to any later phase that wants
  it.**

---

## 4. Corrections to `04-CONTEXT.md` carried into the plans

Both are **agent judgements from reading the files**, not detector results — no detector exists here.

- **D-49 says two of the five generic schema-invariant tests carry `ledger` in their function name. It
  is four**: `test_the_ledger_schema_contains_no_security_definer_function`,
  `test_no_native_enum_type_exists_in_the_ledger_schema`, `test_no_foreign_key_leaves_the_ledger_schema`
  and `test_no_column_in_ledger_has_a_floating_point_type`. Only
  `test_every_timestamp_column_carries_a_time_zone` is already neutral. The rename is a bigger diff than
  the decision anticipated, and a renamed test function is a test id that disappears from saved output.
- **D-47 and D-48 name two Phase 1 files that carry the `ledger` literal. There is a third**,
  `tests/integration/test_migration_chain.py`, and it is the dangerous one because it does **not** go
  red — it goes **blind**. Its four `ledger`-scoped constants mean a pristine-cluster upgrade would
  assert nothing about whether `history` arrived, and the idempotency snapshot would not notice a seed
  applied twice. Widened in plan 04-01, with the registry row count added to the snapshot.

---

## 5. Handed forward, with a named owner

| Item | Owner | What the owner needs to know |
|---|---|---|
| **`request_id` is logged and is not in `LOGGABLE_FIELDS`** (`src/prope/call_ledger/schemas.py:442`, in a function whose docstring argues A-046 four lines above) | **Recorded as a Broken Window** in `.planning/WINDOWS.md` by plan 04-04's executor, in both the table and the JSON block with `open_count` corrected | The fix is one word — `request_id` is ADR-0003's error-envelope correlation id, an identifier and not a body — but it is a Phase 2 omission in a Phase 2 file and importing it into Phase 4's verification would make a green Phase 4 depend on a judgement about call-ledger's error envelope |
| **The A-046 AST gate** — every keyword argument to a structlog call under `src/prope/` must be a `LOGGABLE_FIELDS` member | **Phase 6** (AC-8) | Two known properties, so that phase does not rediscover them: it goes **red on arrival** until `request_id` is added, and it **cannot see dynamically-built payloads** (`log.info(event, **fields)`) |
| **A shared identifier helper for prefixed ULIDs** | **Phase 7** | `EVENT_ID_PREFIX = "hev_"` plus an inline f-string is the third instance of a pattern already written twice (`prc_`, `req_`); a helper introduced now would have to refactor `api.py` and `schemas.py` to be worth anything. Phase 7 adds four prefixes at once and is where the sixth call site appears. **What it must never become**: a registry mapping types to prefixes, which is the auto-discovery shape D-13 refuses |
| **Each writing module registers its own `detail_keys`** — no phase owns this obligation | **Phases 10, 13, 16, 22** (natural homes) | Twenty-nine of thirty-one actions ship with an **empty** allow-list, which refuses any key at all on them — loudly, which is A-124's friction landing where A-124 says it should. Captured in `OQ-029` |
| **The `detail_keys` count is SEVEN of thirty-one declared, not three** — and four of the seven are seeded empty on purpose | **Phase 16** (the four `eval_*` actions) · **whoever adjudicates `OQ-029`** (the count) | Added at plan-critique resolution. `evaluation.lock.yml:94-97` declares that `eval_suite_updated`, `eval_run_started`, `eval_run_completed` and `eval_run_interrupted` each carry *"the prompt_id, version_id, suite_version, and actor"*; `prompt_id` → `scope_prompt_id` and `actor` → `actor_id` are columns, but **`version_id` and `suite_version` are not, so they are `details` keys declared today in a lock file that exists.** They are still seeded empty, because Phase 16 is the module that will write them and should register them with its own test. **The named consequence: Phase 16 writing `eval_run_started` with `details={"version_id": …}` against this seed is refused with `unknown_detail_key`** — the lock's own *"the realistic cause is a rename shipping half-applied"* failure mode arriving from the seed instead. `04-CONTEXT.md` D-61 and plan 04-01's seed comment are corrected; `OQ-029` still carries the stale "3 of 31" in its own text and should absorb this when adjudicated. **`OQ-029` is not edited from here** — `docs/` is read-only to this phase beyond creating an OQ file |
| **`record_event` is a rename target, not a second seam** | **Phase 5** | `docs/modules/property-history.lock.yml` `apis.exposes` names exactly three internal functions — `append(event)`, `read(scope, cursor, limit)`, `registered_actions()` — and `record_event` is none of them. This is a **tension inside the authorities themselves**, not a planner's convenience: ROADMAP puts `append()` in Phase 5 while `.planning/REQUIREMENTS.md` routes PH-05 to Phase 4, and PH-05 is not observable without a write path, so something has to give. D-64 gives the name. **INT-006's `append()` replaces or wraps `record_event`, and `record_event` must not survive as a public name past Phase 5.** Record the spec tension alongside the adoption in `.planning/ORCHESTRATION-DECISIONS.md` so the person adjudicating sees a conflict between two authorities rather than a preference |
| **`HistoryEventDraft`'s eleventh field vs INT-006's ten-field envelope** | **Phase 5** | The draft carries `id` with a `hev_`-prefixed default factory; INT-006's *Envelope carries* names ten fields and `id` is not one of them. Phase 5 owns INT-006's actual signature and reconciles the two — drop the field and return the minted id, or change the spec. Until then `__post_init__` refuses a non-`hev_` id, which closes the cheap half of the hazard |
| **AC-3's arithmetic does not close** — the lock and Phase 5's SC1 both say *"all ten events"* over a lifecycle that enumerates **nine** | **Phase 5** | Not raised as an OQ from outside the phase that owns AC-3; Phase 5 may find the tenth event by reading its own scope |
| **Assignment order is not commit order** | **Phase 5** (cursor pagination) | Two concurrent transactions can take 5 and 6 and commit 6 first, so a *what is new since `seq > N`* poll permanently skips a row that committed after a higher `seq` was returned. INT-007 paginates `seq DESC`, which is the safer direction. **Nothing in Phase 4 exercises two concurrent transactions**, so this is documented, not asserted |
| **Re-deriving the vocabulary for AC-6 is harder than it reads** | **Phase 5** | (a) The five `outputs[].what` values are **prose paragraphs, not lists** — release-control's contains the eight action names *and* the tokens `version_id`, `previous_version_id`, `break_glass`, `set_revision_status`, `A-120`, `ADR-0024`, so a permissive `[a-z_]+_[a-z]+` regex extracts more than eight and makes the "no extras" half fail for the wrong reason. Extract per module, assert **both** directions **and** the per-module count, using the counts the specs themselves declare in `property-history.lock.yml` `inputs`. (b) **`PyYAML` is not a declared dependency** — it resolves only as a transitive of `uvicorn[standard]`, so an `import yaml` in a Phase 5 test passes **by accident** and breaks the day somebody narrows that extra. Add it to the dev group with its reason, or read the lock files as text |
| **No fixture of the 31 names is committed** | **Phase 5** | Deliberate. A committed derivation table would be a seventh copy of a list AC-6 exists to stop copying, and its failure mode is the worst available: the fixture and the migration agree, the lock files have drifted, and the test is green. `04-CONTEXT.md` D-60 and plan 04-01 Task 1 carry the derivation as prose, which is a baseline to check against rather than a source to compare with |
| **`.planning/STATE.md` names Phase 7 as the first phase that must shrink `EXPECTED_ABSENT_SCHEMAS`** | **The orchestrator, at phase close** (ORCHESTRATION §9.6) | It is now wrong: Phase 4 creates `history` and is first. The comment inside `test_tenant_coverage.py` that says the same thing is corrected by plan 04-01 in the same change; the STATE line is not a planner's file to edit |

---

## 6. Pre-existing, still open, and not this phase's to fix

- **`uv run ruff format --check` fails repo-wide** on the `line-length` disagreement (`ruff.toml` says
  120, the repo is hand-wrapped to ~100). Broken Window #1. Every plan in this phase writes new files in
  the house ~100 style so they read like their neighbours, lists `ruff check` as its gate, and **does
  not list `ruff format --check`**, which is unsatisfiable without a repo-wide decision nobody has made.
- **The root `Dockerfile` and `docker-compose.yml` are boilerplate from another project.** Recorded in
  Phase 2's `deferred-items.md` and unchanged. The deployment stack owns no milestone. Repeated here in
  one line only so a planner reading this repo finds them known rather than as the shape to extend.

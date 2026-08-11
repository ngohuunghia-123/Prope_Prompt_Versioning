# Phase 13 — deferred items, mappings, and the planner's own self-check

**Phase:** 13 — Schema, immutability, the constraint, the trigger, and the diff · **Module:**
prompt-registry · **Milestone:** M5 Prompt Registry (**opens it**) · **Depends on:** Phase 12

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections — the twenty `D-NN` decisions with their rejected alternatives and reversibility ratings, and
the re-ground instruction each plan opens with. Everything the deleted *checks* would have caught is
self-checked in §7 below. **Every judgement in this file is an agent judgement made by reading files.**
No deterministic detector exists in this environment and nothing here is detector output.

**This phase OPENS milestone M5, so ORCHESTRATION §9a does not bind it.** The lock-file
`acceptance_criteria` / `test_plan` clause-by-clause walk is **phase 15's**, which closes M5. §4 below is
what phase 15's planner and verifier inherit.

Executors append to this file. Do not renumber the sections — six plans cite these numbers by name.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range was **OQ-070 through OQ-074** and **all five were consumed.** Every one is a real
spec conflict found while planning; none is a placeholder.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-070** | BR-03 as a *database constraint* needs a column `prompt_property` does not declare. A `CHECK` cannot read another table's row; a foreign key to a subset needs `released_version_status`; a trigger is the only column-free option and is procedural | medium | `prompt-registry.lock.yml` `data.owns.prompt_property.fields` |
| **OQ-071** | The one declared cross-schema foreign key collides with the project-wide *no foreign key leaves the schema* invariant, and phase 10's D-171 routed a **composite** version of it to this phase. Phase 13 declines both, in the open | medium | `provider-access.lock.yml` `data.referenced_by`; `prompt-registry.lock.yml` `data.owns.revision.fields` |
| **OQ-072** | `prompt_property.status` has **no declared vocabulary anywhere**. ADR-0053's five literal statuses contribute exactly one value to it (`Retired`); the other four are revision statuses or derived | medium | `prompt-registry.lock.yml` `data.owns.prompt_property.fields`; `ADR-0053` rule 9 |
| **OQ-073** | The model name is *case-insensitive* in A-021 and case-**sensitive** in the lock's declared `unique(workspace_id, namespace, name)`. The gateway resolves a bare model name on the hot path, so the ambiguity is product-visible | low | `A-021.md`; `prompt-registry.lock.yml` `data.owns.prompt_property.notes` |
| **OQ-074** | The search corpus is the *latest* revision's body regardless of status, so the body production is actually serving becomes un-findable the moment a `Draft` is saved on top of it. Correct behaviour, undocumented consequence | medium | `ADR-0048` Decision → *Content*; the owed **AC-11** comment block |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file. **All five files were written at planning time**, before any plan executes — so
`git status --porcelain docs/` must be **empty** for every plan in this phase, and plan 13-06's phase
gate asserts exactly that. Every plan carries a `# READ-ONLY and deliberately NOT in files_modified`
block saying so, because a path listed as modified that the plan forbids writing is a declaration the
orchestrator cannot trust.

Highest OQ id on disk when this phase was planned was **OQ-064** (phase 10's range ended at 059; a
concurrent planner holds 060-064). The range 070-074 was pre-allocated by the orchestrator; **OQ-065
through OQ-069 and OQ-075 onward belong to concurrent planners and this phase claimed none of them.** No
collision.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, and every other phase's directory. In particular **`REQUIREMENTS.md` is not ticked by any
plan here** — plan 13-06 Task 3 reports the requirement → proving-test pairs so the verifier ticks them
from a stated diff (ORCHESTRATION §11's bookkeeping rule).

---

## 2. Mappings

### 2a. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 13) | Owning plan | Requirement | Proven by |
|---|---|---|---|---|
| 1 | Saving an edit to a prompt with 3 revisions creates a 4th with author and timestamp, and revisions 1–3 are byte-identical to before the save | **13-02** (Task 2) | PR-01 | `tests/integration/test_revision_immutability.py` — a column-by-column snapshot with the column list derived from `information_schema.columns`, plus `tests/security/test_revision_append_only_privilege.py` for the privilege that makes it structural |
| 2 | A diff of two revisions renders a line-level body diff plus a field-level comparison of provider, upstream model, parameters and fallback answer in under 300 ms with both bodies at the 32 KiB cap | **13-05** (Task 3) | PR-02 | `tests/integration/test_revision_diff.py` — p95 over repeated runs at `MAX_BODY_BYTES`, on both the reading and the pure path, plus the pathological pair inside the same budget; `tests/unit/test_revision_diff.py` for the semantics |
| 3 | Retiring a prompt with an active release is refused with a message naming the release, and the status is unchanged | **13-03** (Task 2) | PR-05 | `tests/integration/test_retire_guard.py` — the command's refusal naming the version id and revision number with the status read back as `Active`, **and** the same row shape refused by `ck_prompt_property_retired_has_no_release` with the application bypassed |
| 4 | `set_released_revision` against a Draft revision is rejected **by the database**, and the pointer is unchanged | **13-01** (Task 4) | PR-06 | `tests/integration/test_released_pointer_constraint.py` — raw SQL as `prope_app` with the application bypassed entirely, a positive control on the `Approved` path, the `CHECK` half asserted separately, and a drop-and-restore mutation check |

**Four criteria, four owning plans, none claimed twice and none unclaimed.**

**SC4 ships whole, and the shape of the assertion is the point.** A test that `set_released_revision`
refuses would prove nothing about SC4 — that function does not exist until phase 14, and a test of it is
a test of application code. The claim is that **the engine refuses when the application is bypassed
entirely**, which is why plan 13-01 Task 4 forbids importing anything from `prope.prompt_registry` beyond
`domain` constants, and why it carries phase 1's drop-and-restore mutation check verbatim in spirit.

### 2b. Requirement → plan. Each appears in exactly one plan's `requirements:`.

| Requirement | Plan | Lock AC | Status after this phase |
|---|---|---|---|
| **PR-01** | 13-02 | AC-1 | proven |
| **PR-02** | 13-05 | AC-2 | proven |
| **PR-05** | 13-03 | AC-5 | proven |
| **PR-06** | 13-01 | AC-6 | proven |

`requirements: []` on plans **13-04** and **13-06**, deliberately: 13-04 discharges three *owed*
acceptance criteria that PITFALLS gap 1 records and that no requirement id points at (search has no
requirement — PITFALLS gap 5 says so explicitly), and 13-06 is the phase gate plus the owed AC-9. The
same posture is precedented at 03-04, 04-04, 05-01, 05-02, 06-05, 06-06, 07-01, 07-03, 07-06, 08-03 and
08-04.

**PR-03 (private by default) is phase 15's and PR-04 (the seams) is phase 14's.** Neither appears here.

### 2c. The owed acceptance criteria — which of the five this phase takes, and which it routes

PITFALLS gap 1 records **AC-7 through AC-11** as owed to prompt-registry and split between phases 13 and
15. The split this phase chose, and the reason for each:

| Owed AC | Substance | Taken here? | Where |
|---|---|---|---|
| **AC-7** | `search_text` absent from every response body, by a **whole-response scan** | **routed to phase 15** — structural half here | Nothing in phase 13 serves a response and a scan needs endpoints. Phase 13 carries the two structural halves: the column is unwritable by the application (13-01's grant matrix) and unselectable by any statement in the package (13-04's source gate, clauses 2 and 3) |
| **AC-8** | The trigger exists **and fires on a direct `INSERT` bypassing the application** | **taken** | 13-04 Task 2, `tests/integration/test_search_text_trigger.py`, with a drop-and-restore check proving the assertion is about the trigger |
| **AC-9** | `registry.revision` has RLS with a policy and appears in ADR-0045's coverage walk with no exemption | **taken** | Structurally in 13-01 (the column, the policy, `EXPECTED_ABSENT_SCHEMAS` shrunk, no `GLOBAL_TABLES` entry); behaviourally in 13-06 Task 1 |
| **AC-10** | Substring semantics end to end — `'thentic'` matches `authentication`, `'refund'` matches `support/refund-classifier` | **taken at the SQL layer**; end-to-end half routed to phase 15 | The semantics are a property of the trigger's output and the index's operator class, both of which land here. 13-04 Task 2 asserts them against the query; phase 15 re-asserts through `GET /api/v1/prompts` |
| **AC-11** | A term matching only a non-latest body returns nothing; one matching an older **change summary** returns the prompt | **taken** | 13-04 Task 2. This is the corpus decision and the corpus is built here |

**Phase 15 therefore inherits: AC-7 whole, and AC-10's end-to-end half.** Nothing is claimed twice.

---

## 3. Routed to phase 14 — things phase 13 discovered that phase 14 will otherwise re-discover late

Phase 14 was planned **concurrently with this phase, by a different agent**, so every item here is a
possible collision as well as a hand-off. The orchestrator should read this section before fanning out
phase 14.

1. **`set_released_revision` writes THREE columns, not one.** `released_version_id`,
   `released_version_status = 'Approved'` and `released_at` move together, and
   `ck_prompt_property_released_pointer_is_whole` refuses any partial move.
   `clear_released_revision` NULLs all three. The literal `'Approved'` comes from
   `domain.RELEASABLE_REVISION_STATUS`, which **enforces nothing** — the foreign key does — and any code
   that reads it in order to *decide* is the `if` BR-03 forbids. (D-221, OQ-070.)
2. **`set_released_revision` catches the `IntegrityError` and re-raises a domain error naming the
   revision. It does not check the status first.** That ordering is what keeps BR-03 out of Python while
   still giving a reviewer a sentence, and it is the answer to the "a foreign key gives a bad message"
   objection D-221 records.
3. **`set_revision_status` has a transition it cannot perform**, and no authority says so. Moving a
   **currently-released** revision away from `Approved` changes a key the released pointer references and
   is refused by the engine. Correct — un-approving what production is serving should require a
   withdrawal first — but INT-012 does not mention it and phase 14 must decide what the caller sees.
4. **The domain error vocabulary already exists and phase 14 maps it, never re-invents it.**
   `PromptBodyTooLarge`, `ChangeSummaryTooLong`, `ChangeSummaryRequired`, `InvalidModelName`,
   `RevisionNumberConflict`, `PromptPropertyNotFound`, `PromptHasActiveRelease`, `PromptAlreadyRetired`,
   `RevisionNotFound`, `RevisionsNotComparable`. Each carries **identifiers and numbers, never text
   fragments** (A-046), and each docstring names the HTTP shape INT-024 implies without doing the
   mapping.
5. **The write commands exist. Phase 14 mounts routes over them.** `register_prompt_property`,
   `create_revision`, `get_revision`, `update_prompt_property`, `retire_prompt_property`,
   `find_prompt_ids_by_keyword`, `compute_diff`, `get_diff`. Every one takes the actor as a parameter and
   **decides no permission** — the `may()` / `visible_subject_filter` calls are the edge's, which is
   phase 14's. A phase-14 plan that rebuilds these commands is duplicating work, and one that adds a
   second permission check inside them puts BR-01's answer in two places.
6. **`RevisionDiff.exact` must be serialised, and it needs a `vi` catalogue key.** A degraded diff that
   renders identically to an exact one is the silent failure this project keeps refusing. The sentence a
   client shows — *"this comparison is too large to align line by line; the whole body is shown as
   replaced"* — is a keyed message under ADR-0053, and an untranslated boolean is a key nobody added.
7. **The keyword predicate is `search.MATCH_SEARCH_TEXT` and the fold happens on both sides.** Phase 14's
   list query composes RLS (invisible), `visible_subject_filter`'s set form and this predicate — three
   filters, none substituting for another (ADR-0048). `tests/architecture/test_registry_search_statements.py`
   walks the **whole package**, so a phase-14 query that folds differently, adds `SELECT *`, selects
   `search_text`, or reaches for `tsvector` is a red test on the day it is written.
8. **`prope_registry_resolve_duration_seconds`, `resolve_miss_total` and `unfiltered_query_total` are
   already defined at import** with closed label sets and buckets (13-01, D-228). Phase 14 adds
   **increment sites**, not definitions, and phase 15 owns the tripwire's.

---

## 4. Routed to phase 15 — what the milestone-closing phase inherits

ORCHESTRATION §9a binds **phase 15**, not this one. What that phase's clause-by-clause walk must pick up:

- **AC-7 whole, and AC-10's end-to-end half** (§2c above).
- **`test_plan.load` — untouched by this phase.** *"1,000 prompt properties × 20 revisions; search
  p95 < 500 ms; resolve p95 < 10 ms at 50 rps."* The resolve half is **phase 14's** (its SC1 states it);
  the **search half is unowned by any ROADMAP success criterion** and is the clearest candidate for phase
  15 to absorb. `prope_registry_search_duration_seconds` and its buckets exist and are observed
  (13-04), so the instrumentation is already in place.
- **`test_plan.chaos` clause 3** — *"database connection lost mid-create; assert no orphan revision and
  no orphan history event."* Phase 13 asserts the transactional property by making `append` raise
  (13-02); it does **not** provoke a lost connection. Named here so it is absorbed rather than assumed.
- **`test_plan.chaos` clause 1** — *"provider-access unavailable during editor open."* The lock's own
  amended `failure_modes` row records that this state cannot exist (same process, ADR-0026/0033) and
  rewrites the scenario as a failed upstream refresh. Phase 15 should assert the **rewritten** form or
  route it, never the literal text — PITFALLS' standing instruction.
- **`performance_requirements`' revision-create row** — *"p95 < 300 ms, includes the history append in
  the same transaction."* Phase 13 asserts the transaction, not the latency. Unowned today.
- **`observability_requirements.alerts`** — three alert rules, none written by this phase.
  `RegistryUnapprovedPointer`'s query is the interesting one: with D-221's foreign key in place it is
  **structurally unable to return a row**, which is worth writing into the rule's description rather than
  leaving as a coincidence.
- **The route-table uniqueness test** — PITFALLS gap 5's last bullet says it *"cannot actually run until
  every module is mounted, i.e. not before phase 23."* Not this phase's and not phase 15's either; noted
  so nobody looks for it here.

---

## 5. Decisions — `D-220` through `D-239`, all twenty consumed

Continuous project-wide numbering, never restarting. Phase 1 used D-01…D-08, phase 2 D-09…D-25, phase 3
D-26…D-45, phase 4 D-46…D-65, phases 5–9 D-66…D-145, phases 10–12 D-146…D-219. **Phase 14 starts at
D-240** unless a concurrent planner holds that range.

| # | Plan | Decision | Reversibility |
|---|---|---|---|
| D-220 | 13-01 | The whole `registry` guarantee stack ships in ONE revision | costly |
| D-221 | 13-01 | **BR-03 is a foreign key to a subset**, not a trigger and not an `if`. Needs `released_version_status` → OQ-070 | one-way |
| D-222 | 13-01 | Every intra-schema foreign key carries `workspace_id` in both halves (referential integrity bypasses row security) | costly |
| D-223 | 13-01 | **NO FOREIGN KEY LEAVES `registry`** — declines the composite key phase 10's D-171 routed here → OQ-071 | cheap on this side |
| D-224 | 13-01 | `prompt_property.status` is `Active \| Retired` → OQ-072 | costly |
| D-225 | 13-01 | The model name's uniqueness is case-insensitive; `namespace` / `name` take no UPDATE grant → OQ-073 | cheap |
| D-226 | 13-01 | `search_text` is written by the trigger and by nothing else, and the grant matrix says so | cheap |
| D-227 | 13-01 | One composer function, two triggers, one computation site | cheap |
| D-228 | 13-01 | All six declared metrics defined at import, in a per-module observability module | cheap |
| D-229 | 13-05 | The quadratic guard `autojunk=False` removes is replaced by a **counted** one, and a degraded diff reports `exact = False` | costly |
| D-230 | 13-05 | The diff is a pure function; reading the two revisions is a separate half | cheap |
| D-231 | 13-02 | Revision number allocated in the transaction, arbitrated by the unique constraint, retried **once in a new transaction** | cheap |
| D-232 | 13-03 | The retire refusal is a domain error naming the release; the engine constraint is the backstop | cheap / costly |
| D-233 | 13-03 | One event per changed fact, and **no event** for a field the closed vocabulary has no name for | cheap |
| D-234 | 13-03 | An owner transfer is an ordinary update; nothing denormalises the owner's name, which is what keeps OQ-008 cheap | cheap |
| D-235 | 13-04 | One folded statement, in one module, folding both sides with the same two SQL functions — never in Python | costly |
| D-236 | 13-04 | A source gate over the whole package (no `tsvector`, no `SELECT *`, no `search_text` in a select list, no one-sided fold) | cheap |
| D-237 | 13-01 | The two A-050 caps are enforced twice — at the edge for the message, at the engine for the second writer — and the body cap is measured in **bytes** | cheap |
| D-238 | 13-02 | `register_prompt_property` lands private, `Active`, with no released pointer | cheap |
| D-239 | 13-02 | The two A-050 checks run before any transaction opens, and name a size rather than a fragment | cheap |

**Plan 13-06 records no decision, deliberately.** It builds nothing; inventing one to fill a slot would
be the hidden-decision failure §10a warns about, inverted.

---

## 6. `UNCONFIRMED` adoptions — the human-decision list for `13-UAT.md` and `ORCHESTRATION-DECISIONS.md`

Under `mode: yolo` a one-way decision is written in full, adopted, and marked `UNCONFIRMED` rather than
blocking (ORCHESTRATION §6). **None of these violates a §2 non-negotiable** — D-221 exists to *satisfy*
one — so none stops.

| # | Adoption | Plan | Reversibility | What a human is actually being asked |
|---|---|---|---|---|
| 1 | **`subset-fk`** — BR-03 as a foreign key to a subset, adding `released_version_status` to `prompt_property` | 13-01 Task 1 | **one-way** | Not the mechanism but the column: should `data.owns.prompt_property.fields` gain it, or is the trigger form preferred? One migration either way, **only while the pilot holds no releases** (A-020). OQ-070 |
| 2 | **Decline phase 10's D-171 composite foreign key** into `provider.provider_config` | 13-01 (D-223) | cheap on this side | AC-3's *"cannot be bound to a revision"* is now carried by nothing in the database. Confirm, or say what moves: `uq_provider_config_bindable` gains `workspace_id`, the no-FK-leaves-schema invariant gains a written exemption, and the revision field list gains a column. OQ-071 |
| 3 | **`prompt_property.status = Active \| Retired`** | 13-01 (D-224) | costly | Confirm the value set and the new `vi` catalogue key. `Active` makes ADR-0053's *"five statuses"* six on the day this ships. OQ-072 |
| 4 | **Case-insensitive model-name uniqueness** | 13-01 (D-225) | cheap | `ecom/agent` and `Ecom/Agent` cannot both exist. Confirm — or confirm the case-sensitive reading and say which of two same-name-different-case properties the gateway resolves, which no authority states. OQ-073 |
| 5 | **`MAX_DIFF_CANDIDATE_PAIRS = 2_000_000`, and a degraded diff reporting `exact = False`** | 13-05 (D-229) | costly | Confirm the trade — a coarse whole-body diff instead of an exact one that takes seconds — and the sentence the SPA shows. The constant is a judgement that plan 13-05 Task 3 converts into a measurement; the executor records the figure |
| 6 | **`private` as a default argument** rather than a required one on `register_prompt_property` | 13-02 (D-238) | cheap | Confirm that BR-01's answer belongs in a default rather than at every call site |
| 7 | **Editing a `Retired` prompt raises** | 13-03 Task 1 step 2 | cheap | **No authority says either way.** Confirm that terminal means terminal for metadata too, or that a retired prompt's title stays editable. Labelled an agent judgement at the code as well as here |
| 8 | **No history event for a title / purpose / tag edit** | 13-03 (D-233) | cheap | Confirm, or say the vocabulary should gain a `property_edited` name — which is **property-history's** change, not this module's. Related to the existing OQ-028 |
| 9 | **The search corpus stays the latest body regardless of status** | 13-04 / 13-01 | costly later, cheap now | ADR-0048's specified behaviour, implemented and asserted. Confirm, or add the released body to the corpus — one sub-select and one trigger event, cheap only before the pilot holds data. OQ-074 |

---

## 7. The planner's own self-check

The critic stage is deleted for phases 5–24. These are the checks it would have run, run by the planner
against its own output. **All are agent judgements from reading files.**

### 7.1 Every ROADMAP success criterion is owned by exactly one plan

Checked in §2a. SC1 → 13-02, SC2 → 13-05, SC3 → 13-03, SC4 → 13-01. Four criteria, four plans, no
duplicates, no orphans. **Pass.**

### 7.2 Every requirement id appears in exactly one plan's `requirements:`

Checked in §2b. `PR-01` → 13-02, `PR-02` → 13-05, `PR-05` → 13-03, `PR-06` → 13-01. Plans 13-04 and 13-06
carry `requirements: []`, which is precedented eleven times in phases 3–8. No requirement appears twice
and none is missing. **Pass.**

### 7.3 Every file named in a task's `<action>` or `<files>` appears in that plan's `files_modified`

Read back line by line, per plan. **Pass**, with three corrections made during the check and recorded
here so the process is auditable:

- 13-01's read-only block did not name `src/prope/db/metadata.py` or `tests/security/__init__.py`, both
  of which Task 2 and Task 3 prose reference. Added as explicit read-only entries.
- 13-03's read-only block did not name `src/prope/prompt_registry/revisions.py`, whose `get_revision`
  Task 2's test 5 calls. Added — plan 13-02 owns that file and 13-03 must not edit it.
- 13-05's read-only block did not name `tests/load/`, which Task 3's prose tells the executor to follow
  for percentile style. Added.

**The wave-3 disjointness claim, checked explicitly**, because it is the one the orchestrator acts on:
13-03 writes `domain.py`, `properties.py` and two `tests/integration/` modules; 13-04 writes `search.py`,
`observability.py`, two different `tests/integration/` modules and one `tests/architecture/` module. **No
overlap.** Both are forbidden from editing `tests/prompt_registry/__init__.py`, in writing, for exactly
this reason. Every other pair of plans sits in different waves.

### 7.4 Every symbol, fixture, constant and file a plan tells an executor to extend exists, or is created earlier

Checked by grep against the tree and against the plans of phases 4–12. **Pass, with the two contingencies
below written into the plans rather than assumed.**

| Thing | Where it comes from | Status |
|---|---|---|
| `assume_migrate_role`, `reset_role`, `enable_tenant_rls`, `grant_table` | `alembic/ddl.py` | **exists today** |
| `grant_column_update` | plan **10-01** (phase 10 executes before 13) | contingency written into 13-01 Task 2 step 0: add it in 10-01's shape if absent, and say so |
| `GENERIC_SCHEMAS`, and the four renamed generic tests | plan **04-01** | contingency written into 13-01 Task 3: do the rename here if phase 4 did not, in 04-01's stated shape, and do **not** copy the rules into a registry-specific file |
| `SCHEMA_TABLES`, `LIST_OWNED_TABLES` | plan **04-01** | same contingency, same place |
| `truncate_owned_tables` / `LIST_TRUNCATABLE_TABLES` | plan **04-01** | 13-01 Task 3 says to use whatever names are on disk |
| `EXPECTED_ABSENT_SCHEMAS`, `GLOBAL_TABLES`, `DECLARED_SCHEMAS` | `tests/architecture/test_tenant_coverage.py` | **exists today**, and contains `"registry"` |
| `append(session, event) -> str`, `HistoryEventDraft` (ten fields, no `id`) | plan **05-01**, D-67 | re-ground instruction in 13-02 and 13-03; follow the code and report drift |
| `property_created`, `revision_created`, `retired`, `owner_changed`, `access_level_changed` with empty `detail_keys` | plan **04-01**'s seeded registry | re-ground instruction in 13-02 and 13-03: **use the names in the registry table**, not the names in the plan |
| `AccessLevel.PRIVATE` / `.WORKSPACE` in `src/prope/access_control/domain.py` | plan **07-01** | re-ground instruction in 13-01; 13-01 Task 3 adds a test asserting the CHECK's literal set equals the enum's values |
| `migrate_engine`, `app_engine`, `app_sessionmaker`, `report_engine` fixtures | `tests/conftest.py` | **exists today** |
| `WORKSPACE_A` / `WORKSPACE_B` and the `call_record_values` helper shape | `tests/security/__init__.py` | **exists today** |
| `workspace_transaction` | `src/prope/db/session.py` | **exists today** |
| `from ulid import ULID` minting idiom | `src/prope/call_ledger/api.py` | **exists today** |
| `pg_trgm`, `unaccent`, `difflib`, `python-ulid` | bundled contrib / stdlib / already pinned | no `uv add` anywhere in this phase |
| `uq_provider_config_bindable`, `provider_config.bindable` | plan **10-01** | referenced **only** in OQ-071 as the thing this phase declines to aim at. Nothing in any plan depends on it |

### 7.5 The five mechanical prohibitions

- **No plan hardcodes an Alembic `down_revision`.** Only 13-01 adds a revision, and its `files_modified`
  carries the `000N` placeholder comment instructing the executor to read `uv run alembic heads` and wire
  it then. Its Task 2 repeats the instruction and its acceptance criteria assert the number was read
  rather than copied. **Pass.**
- **No plan gates on `ruff format --check`.** Every plan's `<context>` states that it fails repo-wide on
  Broken Window #1 and is not a gate; `uv run ruff check src/ tests/ alembic/` is the gate in all six.
  **Pass.**
- **No plan references a `gsd-core` path.** Every `<context>` block is `@`-prefixed project files only.
  **Pass.**
- **The whole-suite `uv run pytest -q` appears only in the last plan's `<verification>`.** 13-01 through
  13-05 name targeted paths in every `<verify><automated>` and every `<verification>` block; 13-06 Task 3
  is the single whole-suite run, per ORCHESTRATION §10a. **Pass.**
- **No plan adds mypy, a `typecheck` target, a fifth `SECURITY DEFINER` function, a second broker queue,
  `tsvector`, or any other recorded rejection.** 13-01 and 13-04 assert the absence of the first two of
  those in the `registry` schema and in the package's SQL respectively. **Pass.**

### 7.6 Scheduling notes the orchestrator needs before fanning out

**Three plans must run ALONE** (ORCHESTRATION §7a):

- **13-05** — clause (a), a latency assertion. §7a already names phase 13's diff by name.
- **13-01** — clause (b), shared-container-state mutation. Task 4 **drops and restores a foreign key** on
  the session-scoped Postgres container. A concurrent test inside that window could write an unapproved
  released pointer and see it succeed, and that failure would look like BR-03 being broken.
- **13-03** and **13-04** — clause (b) as well. 13-03 Task 2 drops and restores
  `ck_prompt_property_retired_has_no_release`; 13-04 Task 2 drops and restores the `revision_touches_parent`
  trigger, and 13-02 Task 3 grants and revokes `UPDATE (body)`. **In practice that is every plan in this
  phase except 13-06**, so the honest reading is: **phase 13 runs serially, plan by plan.** Waves 1→2→3→4→5
  express the correctness ordering; the file-disjointness of 13-03 and 13-04 is declared for completeness
  and is not an invitation to run them together.

**13-06 runs last and alone**, because it is the phase gate.

### 7.7 What this planner could not check

- **Nothing was executed.** No migration was applied, no test was run, and no PostgreSQL behaviour was
  verified. Two claims in 13-01 are about PostgreSQL rather than about this repository and are labelled at
  the code: that a `BEFORE` trigger assigning `NEW.search_text` needs no column-level `UPDATE` privilege
  (D-226 carries the contingency if it is wrong), and that a composite foreign key over
  `(workspace_id, version_id, status)` needs nothing exotic — which is *why* D-221 rejected the more
  elegant generated-column form.
- **`MAX_DIFF_CANDIDATE_PAIRS = 2_000_000` is an estimate, not a measurement.** Plan 13-05 Task 3 is what
  converts it, and the plan instructs the executor to **move the constant and record why** if the
  just-under-the-ceiling case lands close to 300 ms, rather than shipping a passing test with no headroom.
- **Phases 4 through 12 are planned but not built.** Everything above about `GENERIC_SCHEMAS`, `append`,
  `AccessLevel`, `grant_column_update` and the seeded action vocabulary is a claim about *their plans*.
  Every plan in this phase opens with a re-ground instruction saying exactly that, and naming what to read
  first.

---

## 8. Executor appendix

Executors append below this line: files touched outside a plan's `files_modified` (report as drift, do
not silently absorb), assertions that failed in 13-06 and the follow-up commit that fixed them, the
branch taken for each contingency in §7.4, and the observed p95 figures from 13-05.

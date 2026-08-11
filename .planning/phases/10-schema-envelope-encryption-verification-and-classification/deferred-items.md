# Phase 10 — deferred items, mappings, and the planner's own self-check

**Phase:** 10 — Schema, envelope encryption, verification, and classification · **Module:**
provider-access · **Milestone:** M4 Provider Access (**opens it**) · **Depends on:** Phase 9

Written by the phase planner under the MINIMAL PROTOCOL (ORCHESTRATION §10a). There is no CONTEXT,
RESEARCH, PATTERNS, DISCUSSION-LOG or COVERAGE artifact for this phase, and **no critic reviewed these
plans before execution.** Everything the deleted artifacts carried lives in the plans' `<objective>`
sections — the `D-NN` decisions with their rejected alternatives and reversibility ratings, the two
dependency pins with their arguments, and the re-ground instruction each plan opens with. Everything
the deleted *checks* would have caught is self-checked in §8 below. **Every judgement in this file is
an agent judgement made by reading files.** No deterministic detector exists in this environment and
nothing here is detector output.

**This phase OPENS milestone M4, so ORCHESTRATION §9a does not bind it.** The lock-file
`acceptance_criteria` / `test_plan` clause-by-clause walk is **phase 12's**, which closes M4. §3 and §4
below are what phase 12's planner and verifier inherit; §2 records the one acceptance criterion phase
10 takes off phase 12's hands (**AC-13**) so nobody looks for it twice.

Executors append to this file. Do not renumber the sections — four plans cite these numbers by name.

---

## 1. The phase's whole `docs/` footprint

`docs/` is read-only with exactly one exception: **creating** `docs/brainstorm/open_questions/OQ-NNN.md`.
The allocated range was **OQ-055 through OQ-059** and **all five were consumed.** Every one is a real
spec conflict found while planning; none is a placeholder.

| Id | One line | Severity | Named against |
|---|---|---|---|
| **OQ-055** | Three authorities name three different closed sets of upstream error classes — ADR-0017's eight, INT-015's seven (three spelled differently, two missing), and the lock file's own prose, which uses the ADR's spellings. Five later phases branch on the names and every call record stores one | high | `docs/architecture/interfaces.md` INT-015's error-class list; `docs/adr/0017-…` Decision table; `docs/modules/gateway.lock.yml` `prope_gateway_fallback_total{reason}` |
| **OQ-056** | `credential`'s declared field list carries **one** `nonce` and AES-GCM envelope encryption performs **two** encryptions. The declared list cannot be implemented as written without nonce reuse under the one key that wraps every DEK in the system | medium | `docs/modules/provider-access.lock.yml` `data.owns.credential.fields` |
| **OQ-057** | AC-3's *"cannot be bound to a revision"* has **no declared mechanism** — `data.referenced_by` declares a single-column FK that accepts any configuration, probed or not. Plus: `last_verified_at` has two natural readings and only one works, and a verification writes no history event because the closed vocabulary has no name for one | medium | lock `data.referenced_by`; lock `data.owns.provider_config.fields` (`last_verified_at`); the four-name provider event vocabulary at `outputs → property-history` |
| **OQ-058** | AC-13 refers to *"the re-wrap command"* as though one had been specified. No route exposes it, no `scope.in_scope` clause names it, `events` is empty both ways, and `deployment_target` names no job. PITFALLS gap 1 records it as owed and assigns it to *"10 or 12"* | medium | lock `acceptance_criteria` (the AC-13 comment block); lock `apis.exposes` (the enumerated route list); lock `scope.in_scope` (the rotation clause) |
| **OQ-059** | ADR-0037 says `prope_report` *"reads everything"*; phase 10 makes that untrue by exactly one table. Clause 2 is a **hand-off**, not a question this phase can answer: three declared metric labels are the closest thing in this module to unbounded, and that belongs to phase 12 | low | `docs/adr/0037-…` Consequences; lock `observability_requirements.metrics` — the `provider_config_id` / `upstream_model` label comments |

**Nothing else under `docs/` was written or edited.** No lock file, no ADR, no `interfaces.md` line, no
assumption file. **All five files were written at planning time**, before any plan executes — so
`git status --porcelain docs/` must be **empty** for every plan in this phase, and plan 10-06's phase
gate asserts exactly that. Four plans carry a `# READ-ONLY and deliberately NOT in files_modified`
block in their frontmatter saying so, because a path listed as modified that the plan forbids writing
is a declaration the orchestrator cannot trust.

Highest OQ id on disk when this phase was planned was **OQ-054** (phase 9's range). The range 055-059
was pre-allocated by the orchestrator; **OQ-060 through OQ-064 belong to a concurrent planner and this
phase claimed none of them.** No collision.

**`.planning/` files this phase's planner did NOT touch and its executors must not:**
`ORCHESTRATION.md`, `ORCHESTRATION-DECISIONS.md`, `WINDOWS.md`, `ROADMAP.md`, `REQUIREMENTS.md`,
`STATE.md`, and every other phase's directory.

---

## 2. Mappings — success criteria, requirements, and the one criterion this phase takes off phase 12

### 2a. ROADMAP success criterion → plan. Each owned by exactly one.

| # | Success criterion (ROADMAP, Phase 10) | Owning plan | Requirement | Proven by |
|---|---|---|---|---|
| 1 | An attacker holding the entire database and nothing else cannot recover a credential; supplying the KEK as well recovers it | **10-01** (Task 4) | PA-02 | `tests/security/test_envelope_encryption_roundtrip.py` — a corpus scan over every stored byte in utf-8/base64/hex, then a **subprocess** given the stored columns three ways: no KEK (fails `KekUnavailable`), wrong KEK (fails `InvalidTag`, never a plausible plaintext), right KEK (digest match) |
| 2 | A provider endpoint that returns no usage object fails verification, is not saved active, and cannot be bound to a revision, with the reason naming the missing usage object | **10-03** (Task 4) | PA-03 | `tests/integration/test_provider_must_report_usage.py` (`reason == "no_usage_object"`, row `disabled`/`failed`/`last_verified_at IS NULL`) · `tests/integration/test_unverified_config_cannot_be_bound.py` (a temporary table carrying the composite FK, refused by the engine) · `tests/unit/test_probe_reads_the_usage_object.py` |
| 3 | 429, 500, 401, a content-policy refusal and a bad-parameter 400 each map to their own class with `fallback_eligible` and `retryable` set independently | **10-02** (Task 3) | PA-05 | `tests/unit/test_failure_classification_table.py` — the five statuses as five distinct `ErrorClass` members with the four facts asserted **separately per row**, plus the same-status-two-classes case (400 → `content_filtered` vs `invalid_request`) · `tests/architecture/test_error_taxonomy_is_closed.py` |

**Three criteria, three owning plans, none claimed twice and none unclaimed.**

**SC1 ships whole, and the shape of the assertion is the point.** A test that encrypts and decrypts in
one process proves nothing about SC1 — the claim is over the **stored bytes** and over a process that
holds them and no key. That is why Task 4 is a `subprocess` with a scrubbed environment rather than a
fixture, and why `subprocess` is a `must_haves.artifacts.contains` entry rather than an implementation
detail.

**SC2 ships as a whole criterion with one half of its *mechanism* in another phase.** The refusal is
proven against the live engine here, through a temporary table carrying the same composite foreign
key. What phase 10 cannot do is make `registry.revision` carry that key, because `registry.revision`
does not exist until phase 13. **§3 is that hand-off**, and it is the most important thing in this
file.

**SC3 ships whole and then some** — the shipped set is ten classes, not the five the criterion names,
because two of this module's own refusals (`kek_unavailable`, `admission_shed`) have `origin = prope`
and none of ADR-0017's eight does. Both members are declared here with **no producer in this phase**;
that is deliberate and D-168 says why. `kek_unavailable` gets its producer in **phase 12** (AC-12),
`admission_shed` in **phase 11** (PA-06). A closed set that grows in three phases is not closed.

### 2b. Requirement → plan. Each id in exactly one plan's `requirements:`.

| Requirement | Lock AC | Plan | Note |
|---|---|---|---|
| **PA-02** | provider-access AC-2 | **10-01** | Complete. The subprocess recovery attempt is the whole criterion, both directions |
| **PA-03** | provider-access AC-3 | **10-03** | Clauses 1 and 2 complete; clause 3 (*"cannot be bound to a revision"*) proven against the mechanism, with the referencing half routed to phase 13 — §3 |
| **PA-05** | provider-access AC-5 | **10-02** | Complete. The table is pure, exercised as a table, and asserted closed in both set directions |

**Three requirements, three appearances, no duplicates and no omissions.** No requirement outside
`PA-02, PA-03, PA-05` appears in any phase-10 plan's `requirements:` — checked against
`.planning/REQUIREMENTS.md`'s traceability rows, which route PA-01 to phase 12 and PA-04/06/07/08/09
to phase 11.

`requirements:` is `[]` on plans **10-04**, **10-05** and **10-06**, and that is a fact about
`REQUIREMENTS.md` rather than about the work:

- **10-04** ships the model catalogue. The ROADMAP routes *"the catalogue"* to this phase through its
  **Spec** line (`scope.in_scope` — *"Maintain the model catalogue per configuration"*), and **no
  `PA-NN` requirement names it.** What it satisfies instead is `data.owns.model_catalogue` in full and
  the lock's `test_plan.integration` clause *"catalogue discovery, refresh, manual add, and a model
  going unavailable"*. Phase 11 owns INT-016's route surface (PA-10).
- **10-05** ships rotation-in-place and the KEK re-wrap. **PA-08 is phase 11's**, because its assertion
  is *"in use in every process within 60 seconds"* and the 60 s decrypted-credential cache is phase
  11's. What 10-05 owns instead is **AC-13** — see below.
- **10-06** ships the forbidden-edge source gate, the report-role refusal, the closed-surface inventory
  and the phase gate. Nothing there has a requirement id, and phases 5, 6, 7, 8 and 9 each recorded the
  same thing for their final plan.

### 2c. AC-13 is discharged in phase 10, and phase 12's verifier must not look for it

`.planning/research/PITFALLS.md` gap 1 records **AC-13** as owed, never written as a numbered row in
the lock file, and assigned to *"phase 10 or 12"*. **D-177 assigns it to phase 10, plan 10-05, Task 3.**

The argument: the operation is two columns (`wrapped_dek`, `kek_version`), one crypto function
(`rewrap_data_key`) and one key ring — **all of which are phase 10's** — and `kek_version` would
otherwise be a column with no exerciser for two whole phases. The five clauses are asserted as five
separate facts, including the byte-identity of `ciphertext` and `nonce` across the re-wrap, which is
the proof that ADR-0014's *"it does not touch a single ciphertext"* is true rather than intended.

**Phase 12's planner and verifier should treat AC-13 as closed** and confirm it by reading
`tests/security/test_kek_rewrap_v1_to_v2.py`, not by writing a second one.

**Reversibility of the assignment: cheap** as code (a function with one call site) and **not free as a
decision** — it is `OQ-058`, and the thing a human is being asked is whether a re-wrap should be a
route, a CLI or a job instead of a plain callable invoked by the host that already holds `.env`.

---

## 3. Routed to PHASE 13 — the other half of the binding guarantee. **This is the one that gets lost.**

Phase 10 builds a foreign-key **target** and cannot build the thing that points at it, because
`registry.revision` does not exist until phase 13, which is planned in a different batch by a
different agent three phases away.

**A target nobody aims at is worse than no target: it looks like a guarantee.**

`provider.provider_config` carries, landed by plan 10-01's single revision:

```sql
bindable boolean GENERATED ALWAYS AS (last_verified_at IS NOT NULL) STORED,
CONSTRAINT uq_provider_config_bindable UNIQUE (id, bindable)
```

**Phase 13 must write this on `registry.revision`, verbatim:**

```sql
-- on registry.revision
provider_config_bindable  boolean NOT NULL DEFAULT true,
CONSTRAINT ck_revision_provider_config_is_bindable CHECK (provider_config_bindable),
CONSTRAINT fk_revision_provider_config
    FOREIGN KEY (provider_config_id, provider_config_bindable)
    REFERENCES provider.provider_config (id, bindable)
```

If phase 13 writes the single-column foreign key `data.referenced_by` declares instead, **AC-3's third
clause is enforced nowhere** and the generated column plus its UNIQUE sit in the schema proving
nothing.

**The same DDL appears in five places, deliberately.** `OQ-057` clause 1; this section; the
`COMMENT ON` in plan 10-01's revision; plan 10-03's SUMMARY; plan 10-01's SUMMARY. The failure mode is
not that phase 13 refuses — it is that **phase 13 never hears**, and each of those five is somewhere a
person reading phase 13's inputs would look.

Also routed to phase 13, same subject, lower stakes: `last_verified_at` means **the last verification
that PASSED** (D-170, `OQ-057` clause 2), enforced by a `BEFORE UPDATE` trigger owned by
`prope_migrate`, and recorded in a `COMMENT ON COLUMN` so it is discoverable from `psql`. A phase-13
reader who assumes the other reading — *"the last verification that ran"* — will write a revision
binding that a transient provider blip can break.

---

## 4. Routed to PHASES 11 and 12 — observations, not obligations

Recorded here so they are not lost between two phases planned by different agents. **None claims an id
from another phase's OQ range**; each says which phase should raise it if it agrees.

| # | Observation | Owner | Why it is not phase 10's |
|---|---|---|---|
| **F-10-1** | **Metric label cardinality.** `prope_provider_access_upstream_duration_seconds{provider_config_id, upstream_model}`, `credential_rejected_total{provider_config_id}` and `model_unavailable_total{provider_config_id, upstream_model}` are the closest thing in this module to unbounded label spaces, and a `provider_config_id` resolves to exactly one workspace — which matters the moment a `/metrics` route serves this registry. Phase 10 **ships the labels as declared**, on phase 3's standing rule *do not drop a declared label to avoid raising a question*, and records the exposure at the metric | **Phase 12** | Phase 12 owns `observability_requirements` per the ROADMAP's spec routing, and owns `/readyz` and the metrics surface. It should raise this from its own OQ range. Recorded as `OQ-059` clause 2 and at the metric definition itself |
| **F-10-2** | **A verification writes no history event.** The closed vocabulary carries four provider events and none of them is a verification, so `POST /api/v1/providers/{id}/verify` — a deliberate human action with an actor attached — leaves **no audit row**. It is observable only through `verification_total` and the row's own columns, and a re-verify is therefore not attributable to an actor | **Phase 11** | Phase 11 owns that route and the actor that calls it. Widening a closed thirty-one-name vocabulary is a conversation, not a plan's side effect. `OQ-057` clause 3 |
| **F-10-3** | **`get_model_catalogue`'s declared return shape is short.** INT-016 declares `{model_id, display_name, supports_streaming, available}` and omits `source`, `first_seen_at` / `last_seen_at`, and the `mdl_` id — all of which the table carries and the revision editor's picker plausibly wants (a `manual` row and a `discovered` row are not interchangeable to a person choosing one) | **Phase 11** | Phase 11 implements INT-016. Phase 10 stores every column; it does not decide the seam's projection |
| **F-10-4** | **Store-then-probe ordering on rotation.** `rotate_credential` replaces the stored credential **immediately**; the re-probe A-090 requires is a route-level composition (`rotate_credential` then `verify_provider_config`). So between the two, the stored credential is new and unverified. The alternative — do not replace until a probe passes — needs somewhere to hold the candidate, and that place is a second credential row, which A-025 exists to forbid | **Phase 11** | It is a question about the route's error contract (INT-027), and phase 11 owns the route. Recorded rather than decided from underneath it |
| **F-10-5** | **`registration` and `verification` are two transactions.** `POST /api/v1/providers` is `register_provider_config` then `verify_provider_config`, and a crash between them leaves a **disabled, unverified** row — which is the safe direction, and the reason D-165 saves a disabled row rather than saving nothing | **Phase 11** | Phase 11 composes the route. Phase 10 states the composition in `configs.py`'s module docstring, where a reader will look for it |
| **F-10-6** | **The workspace enumerator for the re-wrap may not exist yet.** `rewrap_all_credentials` is written against *"a function that returns the workspace ids"* — `access.list_workspaces()` from plans 07-01/07-03. If phase 7 has not landed the call site in the shape 10-05 assumes, the re-wrap takes an explicit `workspace_ids` sequence and the enumerator becomes the caller's | **Phase 10's own executor** | It is drift, not a design question. The executor reports what it found in the 10-05 SUMMARY and appends it here |

---

## 5. Plans, waves and dependencies

| Plan | Wave | depends_on | What it is |
|---|---|---|---|
| **10-01** | 1 | — | **Tracer.** Two pinned dependencies, one Alembic revision carrying the whole `provider` guarantee stack, the key ring, the envelope, three models, fourteen metrics, `register_provider_config`, and SC1 asserted from a separate process |
| **10-02** | 2 | 10-01 | SC3. ADR-0017's taxonomy as a table — ten classes, four independent facts each, one pure classifier, and a source gate proving nothing in the package retries |
| **10-03** | 3 | 10-01, 10-02 | SC2. The one httpx construction site, the verification probe, the stub upstream, and the three verification columns |
| **10-04** | 4 | 10-01, 10-03 | The model catalogue: four-case reconciliation, manual rows a refresh never touches, and a failed refresh that changes nothing |
| **10-05** | 4 | 10-01, 10-03 | Rotation in place with its event in the same transaction, and **AC-13** — the KEK re-wrap, clause by clause |
| **10-06** | 5 | all | The forbidden edge as a source gate, the one privilege-level refusal, the closed-surface inventory, the echoing provider, and **the phase gate** |

**The waves were corrected during the planner's self-check.** 10-03 was declared `wave: 2` while
depending on 10-02, which is also wave 2 — a wave number that contradicts its own `depends_on`. Phases
5 through 9 all hold the invariant *a plan's wave is strictly greater than the wave of everything it
depends on*, and phase 10 now does too.

**No two plans in this phase have disjoint `files_modified`.** Five of the six touch
`src/prope/provider_access/observability.py`, because all fourteen metrics are defined once at import
in one module (D-164) and every later plan adds an increment site rather than a metric. 10-03 and 10-04
share `probe.py`, `configs.py` and `tests/provider_access/stub_provider.py`; 10-01 and 10-05 share
`credentials.py`. **The orchestrator's disjointness check will never fan out, which is correct.**
Execution is serial regardless (ORCHESTRATION §7); the waves express correctness ordering only.

**Wave 4's two plans could in principle interleave and must not**, for a reason worth stating: both
extend `observability.py` and 10-05's Task 2 asserts the module still defines **exactly fourteen**
metrics. Running them concurrently makes that assertion a race against another plan's edit.

**Exactly one Alembic revision in the phase**, landed by 10-01. Plans 10-03, 10-04, 10-05 and 10-06
each carry an explicit frontmatter note that they add none — a phase with two revisions in flight is a
phase where `alembic heads` is read twice and wired wrong once.

---

## 6. UNCONFIRMED adoptions — for `10-UAT.md` and `ORCHESTRATION-DECISIONS.md`

`mode: yolo`. Each was decided by the planner on the user's behalf, is written out in full in the
owning plan's `<objective>` and in a `<task type="checkpoint:decision" gate="record-and-adopt">` block
with both options, pros, cons and a reversibility rating, and appears as a `<human-check>` in that
plan's `<verification>`. **None blocks execution.**

**None touches a §2 non-negotiable** — checked row by row. Human approval before production, the
Approved-only database constraint, the three separate permissions and private-by-default are untouched
by every one. The credential constraints (*encrypted at rest, never returned by a read API, redacted
everywhere*) are **strengthened** by U-10-1, U-10-4 and U-10-6 and weakened by none.

| # | Decision | Plan | Reversibility | What the user is being asked |
|---|---|---|---|---|
| **U-10-1** | **D-162** — the DEK's wrap nonce is **prefixed to `wrapped_dek`** (12 bytes ‖ ciphertext) rather than stored in a new `dek_nonce` column, so the lock's declared field list stays literally true | 10-01 | **one-way** — stored bytes under an authenticated cipher; changing the layout after credentials exist means decrypting every credential, which is the migration ADR-0014 exists to avoid | Should `credential`'s field list gain `dek_nonce`? It is cheap only while the pilot holds no real credentials (A-020 holds that line), and it gets cheaper never. `OQ-056` |
| **U-10-2** | **D-167 + D-168** — **ADR-0017's eight class names ship**, extended to ten with `kek_unavailable` and `admission_shed`; INT-015's seven do not | 10-02 | **costly** — phases 16, 18, 19, 20, 21 branch on these names and every call record stores one; a rename after traffic is a rename plus a data migration over `ledger.call_record` | Should `interfaces.md` INT-015's list be corrected to ADR-0017's? And note the named consequence: `prope_gateway_fallback_total{reason=upstream_5xx}` names a value this module will never produce, so **phase 19 must translate or correct the label**. `OQ-055` |
| **U-10-3** | **D-171** — *"cannot be bound to a revision"* is enforced by a **composite foreign key** (`bindable` generated column + `UNIQUE (id, bindable)`), not by an application check in prompt-registry | 10-03 | **one-way on the column** (generated and referenced), **cheap on the phase-13 half** | Should `data.referenced_by` be corrected to declare the composite key? Without it phase 13's planner reads a spec that says something different from the code. `OQ-057` |
| **U-10-4** | **D-166** — `prope_report` is **not** granted `SELECT` on `provider.credential`, the first table in Prope the reporting role cannot read | 10-01 (asserted in 10-06) | **cheap** — one line in a follow-up revision | ADR-0037's *"reads everything and changes nothing"* is now untrue by one table. Amend the ADR, or restore the grant. Note the backup is unaffected: it runs as `postgres`. `OQ-059` |
| **U-10-5** | **D-177** — **AC-13 is asserted in phase 10**, and the re-wrap ships as a plain async function invoked from the host that already holds `.env` — not a route, not an Alembic data migration, not a supervised job | 10-05 | **cheap** as code; the **assignment** is what is not free | Confirm the home, or name the route / CLI / job it should be. And: an unfinished re-wrap is invisible — a mixed corpus works indefinitely — so is the operator's `SELECT DISTINCT kek_version` check enough, or should phase 12 surface it as a readiness or alerting concern? `OQ-058` |
| **U-10-6** | **D-161** — three explicit `SecretStr` KEK slots (`kek_v1..v3`) on the **one** `Settings` class, rather than `extra="allow"` harvesting every `PROPE_KEK_V<n>` | 10-01 | **cheap** — one line per slot | Three is a ceiling: two live rotations can be in flight before anyone edits code. Confirm three, or name the number. The rejection is specific: pydantic extra fields are plain `str`, not `SecretStr`, so a `Settings` repr in a traceback would print every KEK in full |
| **U-10-7** | **D-165** — a registration whose verification later fails saves a **disabled, unverified row**; it does not save nothing | 10-01 | **cheap** | Confirm the row survives so `verification_error` has a reader and the dashboard can show why. The alternative is deleting it, in which case `verification_error` is a column with no writer |
| **U-10-8** | **D-178** — the forbidden edge *anything → credential* is enforced by a **source gate** (an AST walk over an rglob-discovered file list), and the grant matrix is labelled as enforcing something else | 10-06 | **cheap** | Eight modules share one database role by decision (ADR-0027), so a grant cannot see a module boundary. Confirm a source gate is acceptable, or say the boundary needs a mechanism the database can see — which means reopening ADR-0027 |
| **U-10-9** | **D-175** — `supports_streaming` is asserted `True` for every discovered model on the strength of the adapter's name, because the provider's model list does not say | 10-04 | **cheap** | Confirm, or say the picker should show it as unknown rather than as a claim nobody verified |
| **U-10-10** | **D-174** — a refresh **never deletes** and never touches a `manual` row; a model the provider stops listing goes `available = false` and keeps its `first_seen_at` | 10-04 | **cheap** | Confirm a workspace's catalogue only grows for the pilot's lifetime |

---

## 7. Discoveries an executor or a later phase needs, that are not on any plan's happy path

1. **`EXPECTED_ABSENT_SCHEMAS` must shrink in the same change.**
   `tests/architecture/test_tenant_coverage.py` currently lists `provider` among the seven declared-but-absent
   schemas. Plan 10-01 removes it **in the same commit as the migration** and adds **no** entry to
   `GLOBAL_TABLES` — all three `provider` tables are tenant-scoped (ADR-0045), and `credential`
   carrying `workspace_id` is the correction ADR-0045 exists for.

2. **`grant_table(..., report_select=False)` already exists and has never been used.**
   `alembic/ddl.py:97` declares the parameter with a default of `True`. Phase 10 is its **first**
   caller, which is exactly why `OQ-059` exists — a parameter nobody had exercised is a decision
   nobody had made.

3. **`ruff format --check` is not a gate and must never be added to one.** It fails repo-wide on
   Broken Window #1. Every plan states this in its `<context>` and its `<success_criteria>`.

4. **Neither `property_history` nor `access_control` exists on disk yet.** Phases 5-9 are planned and
   **not built**. Every phase-10 claim about `append()`, `HistoryEventDraft`, `credential_rotated`'s
   registry entry or `access.list_workspaces()` is a claim about *plans* 04-01, 05-01, 07-01 and 07-03
   — verified to be specified there, not verified to exist. **Each plan opens with a re-ground
   instruction naming the exact files to read on disk before following its prose, and says the code
   wins.**

5. **The `openai` SDK is deliberately not added in this phase.** The lock names it as a **test-only**
   oracle for AC-9, and AC-9 is phase 11's. Adding it now puts a second HTTP client in the runtime
   dependency tree for nothing. Plan 10-01's acceptance criteria assert it appears in neither
   `[project].dependencies` nor `[dependency-groups].dev`.

6. **`httpx` is pinned in plan 10-01 and used in plan 10-03**, on purpose: `uv.lock` is regenerated
   once rather than by two plans in one phase producing two lock diffs over the same file.

7. **ADR-0047's address-pinning transport is phase 12's, and phase 10 must not foreclose it.**
   `build_upstream_client` in `upstream.py` is the **single** construction site, with the transport as
   a parameter. Nothing in phase 10 may bake a hostname-resolving client into a call site, because
   that is the seam phase 12 has to reach. `follow_redirects=False` everywhere, always — asserted as a
   source gate, not left to review.

8. **Two `ErrorClass` members ship with no producer.** `kek_unavailable` (phase 12) and
   `admission_shed` (phase 11). Their rows in `CLASSIFICATION` are complete today; their increment
   sites are not. Plan 10-02 says which is which at the code so a later reader does not read an unused
   member as dead code.

9. **The re-wrap's operator sequence exists in exactly one place.** `OQ-058` clause 2 carries the four
   steps — add `PROPE_KEK_V2`, run the re-wrap, verify `SELECT DISTINCT kek_version` per workspace,
   remove V1 and restart. Plan 10-05 requires it reproduced **verbatim in `rewrap.py`'s module
   docstring**, because a runbook for an action performed under pressure that lives only in an open
   question is a runbook nobody finds at 2am.

10. **This module never retries, and that is asserted rather than intended.** The lock's `non_goals`
    say so; plan 10-02 Task 3 enforces it as a source gate — no loop encloses an upstream call, no
    transport is constructed with a non-zero `retries`, and every client passes `follow_redirects=False`.
    A later plan that adds a retry reddens a test in `tests/architecture/`, which is the point.

---

## 8. The planner's self-check — because no critic ran

The exec-critic and spec-critic stages are deleted for phases 5-24 (ORCHESTRATION §10a). These checks
were performed by the planner, by reading and grepping, and each is stated with its method so a
verifier can redo it.

**1. Every ROADMAP success criterion is owned by exactly one plan.** ✅
Verified against `.planning/ROADMAP.md` lines 258-262. SC1 → 10-01, SC2 → 10-03, SC3 → 10-02. §2a is
the table. No criterion appears in two plans' `must_haves.truths` as an ownership claim.

**2. Every requirement id in PA-02, PA-03, PA-05 appears in exactly one plan's `requirements:`.** ✅
`grep -H "^requirements:" 10-0*.md` → `[PA-02]`, `[PA-05]`, `[PA-03]`, `[]`, `[]`, `[]`. Three ids,
three appearances, no duplicates, nothing outside the allocated set. Cross-checked against
`REQUIREMENTS.md`'s traceability rows 209-216, which route the other six PA ids to phases 11 and 12.

**3. Every file named in any task's `<action>` or `<files>` appears in that plan's
`files_modified`.** ✅ — and this is the defect class the deleted exec-critic existed to catch.
Method: a script extracted every path-shaped token from each plan's body and diffed it against that
plan's `files_modified` list; every residual was then read in context to confirm it is a **read**, an
authority citation, or another plan's file.

- The union of every `<files>` line in each plan is a **subset** of that plan's `files_modified`, in
  all six. Checked pair by pair.
- Residuals fall into four groups and nothing else: (a) authorities under `docs/` and `.planning/`,
  read and cited; (b) another module's package read for its idiom (`property_history/`,
  `call_ledger/`, `access_control/`, `db/`); (c) existing tests read as precedent
  (`test_report_role_can_read_bodies.py`, `test_append_only_privilege.py`,
  `test_publish_confirm_failures.py`); (d) other phase-10 plans, referenced by name in `<context>`.
- **Two specific traps were checked by hand.** `pyproject.toml` / `uv.lock` appear in 10-03's prose —
  they are a *reference to plan 10-01's Task 2* (*"No new dependency"* is stated in the same
  paragraph), so 10-03 correctly does not declare them. `src/prope/worker.py` appears in 10-05's
  `read_first` — it is read for the `WorkspaceEnumerator` parameter shape (Broken Window #3), not
  edited.
- **The five `OQ-055…059` files were removed from `files_modified` and moved into a labelled read-only
  frontmatter comment**, because they were written at planning time and every plan forbids rewriting
  them. A path declared as modified that the plan forbids writing is a declaration the orchestrator
  cannot trust.

**4. Every symbol, fixture, constant and file the plans tell an executor to extend exists, or is
created by an earlier plan in this phase, or is specified by an earlier phase's plans.** ✅
Grepped, one by one:

| Named | Status |
|---|---|
| `alembic/ddl.py` — `enable_tenant_rls`, `grant_table(report_select=…)`, `assume_migrate_role` | **exists** (`ddl.py:49`, `:97`, `:103`, `:27`) |
| `tests/architecture/test_tenant_coverage.py` — `EXPECTED_ABSENT_SCHEMAS` (contains `"provider"`), `GLOBAL_TABLES` | **exists** (`:45`, `:37`) |
| `src/prope/db/engine.py` — `Settings(BaseSettings)` with `env_prefix="PROPE_"` | **exists** (`:22`, `:32`) |
| `src/prope/db/session.py` — `workspace_transaction`, `create_workspace` | **exists** (`:49`) |
| `tests/conftest.py`, `tests/integration/_asgi.py`, `tests/architecture/test_schema_invariants.py`, `test_no_sql_interpolation.py`, `tests/integration/test_migration_chain.py`, `tests/security/test_report_role_can_read_bodies.py`, `test_append_only_privilege.py`, `test_tenant_isolation.py`, `tests/broker/test_publish_confirm_failures.py`, `tests/unit/test_missing_price_is_unpriced_not_zero.py` | **all exist** |
| `src/prope/property_history/append.py` · `domain.py` · `HistoryEventDraft` | **does not exist; specified by plan 05-01** (`05-01-PLAN.md:73, 176, 304, 382, 448`) — flagged at every call site |
| `credential_rotated` registry entry (`target_type = provider_config`, `detail_keys = {}`) | **specified by plan 04-01's closed vocabulary** — 10-05 re-grounds against it |
| `src/prope/access_control/bootstrap.py` · `workspaces.py` · `access.list_workspaces()` | **does not exist; specified by plans 07-01 / 07-03** (`07-01-PLAN.md:73, 152, 184`) — F-10-6 records the fallback |
| Everything else phase-10 plans "extend" | **created by plan 10-01 or 10-02 within this phase** — `crypto.py`, `keyring.py`, `models.py`, `observability.py`, `credentials.py`, `configs.py`, `failures.py`, `stub_provider.py` |

**5. No plan hardcodes an Alembic `down_revision`, gates on `ruff format --check`, references a
`gsd-core` path, or puts the whole-suite run anywhere but the last plan.** ✅

- `grep -n "down_revision"` → four hits, all **instructions not to hardcode one**: the executor runs
  `uv run alembic heads`, names the file one past the head, and wires it then. The frontmatter
  placeholder is `000N_provider_schema.py` with a five-line comment saying why any number written
  there would be wrong.
- `grep -n "ruff format"` → twelve hits, **every one** of the form *"is **not** a gate"*. No
  `<verify><automated>` and no `<success_criteria>` line invokes it.
- `grep -n "gsd-core"` → **zero hits.** Every `<context>` entry is an `@`-prefixed project path.
- `grep -n "pytest -q"` outside a targeted path → **three hits, all in 10-06**, and all three describe
  the phase gate: `must_haves.truths`, D-179's text, and the `<verification>` block. Every per-plan
  `<verify><automated>` names its own files. 10-06 Task 3's `uv run pytest tests/security/ -q` is a
  directory-scoped corpus scan, not the suite.

**6. Additional checks the planner ran that were not on the list.**

- **`D-NN` range:** D-160…D-179 used, **all twenty, none skipped, none repeated, none outside the
  range.** §9.
- **OQ range:** OQ-055…OQ-059, all five consumed, none outside the range; `OQ-060+` belong to a
  concurrent planner and are untouched.
- **Waves versus `depends_on`:** one violation found and corrected — see §5.
- **The four non-negotiables:** every UNCONFIRMED adoption checked against §2 of ORCHESTRATION. None
  is touched; three strengthen the credential constraints. **No plan is blocked.**
- **`SECURITY DEFINER`:** phase 10 adds none. The monotonicity trigger function is declared
  `SECURITY INVOKER` **explicitly**, and 10-06 asserts the `provider` schema contributes nothing to the
  sanctioned four.
- **Forbidden edges:** no phase-10 plan reaches gateway, evaluation, prompt-registry, call-ledger or
  release-control. `configs.py` calls `property_history.append` and `access-control` is not consumed at
  all in this phase — the management routes that would consume it are phase 11's.

---

## 9. `D-NN` range consumed

**D-160 through D-179 — all twenty.** Continuous project-wide numbering; phase 11 starts at D-180 or
wherever its own allocation begins.

| Id | Plan | Decision |
|---|---|---|
| D-160 | 10-01 | The whole `provider` guarantee stack ships in ONE Alembic revision |
| D-161 | 10-01 | Three explicit `SecretStr` KEK slots on the one `Settings` class |
| D-162 | 10-01 | `wrapped_dek` carries its own nonce; there is no fourth column |
| D-163 | 10-01 | Both encryptions are bound to the row by AAD |
| D-164 | 10-01 | All fourteen metrics defined at import, in a per-module observability module |
| D-165 | 10-01 | A failed registration saves a DISABLED row; it does not save nothing |
| D-166 | 10-01 | `prope_report` is NOT granted `SELECT` on `provider.credential` |
| D-167 | 10-02 | ADR-0017's eight class names are adopted; INT-015's seven are not |
| D-168 | 10-02 | Two `prope`-origin classes are added; the closed set is ten, not eight |
| D-169 | 10-02 | Classification takes status, provider error code and finish reason; never status alone |
| D-170 | 10-03 | `last_verified_at` means the last verification that PASSED |
| D-171 | 10-03 | "Cannot be bound to a revision" is a composite foreign key; phase 13 owns the other half |
| D-172 | 10-03 | The probe lists models first, then completes with a named model |
| D-173 | 10-03 | The HTTP client is a parameter; `upstream.py` is the only place one is built |
| D-174 | 10-04 | A refresh never touches a `manual` row, and never deletes anything |
| D-175 | 10-04 | `supports_streaming` is an adapter-level claim, not a discovered fact |
| D-176 | 10-05 | A rotation is an UPDATE in place, not a delete-and-insert |
| D-177 | 10-05 | AC-13 is asserted HERE, in phase 10; the re-wrap is a callable rather than a route |
| D-178 | 10-06 | The forbidden edge is enforced by a source gate; the grant enforces something else |
| D-179 | 10-06 | The phase gate lives in the last plan, and a failing gate is drift rather than a fix |

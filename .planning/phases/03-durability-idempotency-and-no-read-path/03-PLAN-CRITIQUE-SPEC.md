# Phase 3 — adversarial spec-fidelity critique of the plan set

**Written:** 2026-08-10 · **Role:** critic-spec · **Scope:** every file in
`.planning/phases/03-durability-idempotency-and-no-read-path/`, read against
`docs/modules/call-ledger.lock.yml`, `docs/architecture/interfaces.md`, `docs/adr/*`,
`.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/research/PITFALLS.md` and
`.planning/ORCHESTRATION.md`.

**One question:** would executing these plans build something the spec did not ask for, or fail to
build something it did?

> **No detector was run.** `api-coverage.cjs`, the edge probe and the assumption-delta detector do not
> exist in this environment (ORCHESTRATION §0). Every claim below is an **agent judgement**, reached by
> reading the plans, the authorities and the code they name. Where a finding rests on a fact in `src/`
> or `tests/`, the file and line are cited so the claim is checkable rather than trusted.

---

## What is right, stated so it is not re-litigated

These were checked and are correct. They are listed because a critique that only names defects invites
a reviewer to re-check the things that already hold.

- **PITFALLS §2 is obeyed.** Every plan asserts against the *restated* AC-1 and AC-2, never the lock
  file's literal spill text. `03-01`'s SC1 is "RabbitMQ unreachable" provoked two ways; `03-02` Task 3's
  module docstring is required to state in its first paragraph that it asserts the restated AC-2 and not
  the literal one; `OQ-024` raises the stale `test_plan.chaos` / `test_plan.unit` text rather than
  absorbing it. Correct, and the sharper half — that the stale chaos clause also contradicts the amended
  `/readyz` clause **in the same file** — is a real finding the plans made on their own.
- **PITFALLS §1 routes nothing here.** The sixteen owed-and-never-written acceptance criteria belong to
  prompt-registry, access-control, evaluation, gateway, provider-access and release-control. There is no
  call-ledger row. Nothing is owed to this phase from §1, and no plan invents one.
- **`data.owns` is respected.** No plan creates a table, and `03-CONTEXT.md` says so out loud with the
  instruction that needing one would be information rather than licence.
- **No fifth `SECURITY DEFINER`.** `03-04`'s prohibition list refuses it by name for the
  `oldest_body_age_seconds` enumeration, which is the one place in this phase where the temptation is
  real, and routes the correct answer to Phase 7's enumerator parameter.
- **The forbidden edges hold.** `dependencies: []` and `outputs: []` survive. The fallback reaches
  `prope.db`, which is infrastructure, not a module; `enqueue.py` is explicitly forbidden a database
  import and the prohibition is verified by command.
- **CL-02's real subject is identified correctly.** `03-02`'s objective — that a duplicate in
  `call_record` is refused by the primary key with or without this phase, and that what a redelivery
  actually corrupts is `ledger.workspace_spend` — is the load-bearing insight of the phase, and the
  `RETURNING`-over-`DO NOTHING` design follows from it. `sort_by_parameter_order`'s deliberate absence,
  with the reason written at the statement and a five-plus-two regression test behind it, is exactly
  right.
- **CL-07 is closed against the declared metric.** `03-03` correctly refuses to close SC3 by renaming
  Phase 2's constant, gives `allowed` and `refused` the increment sites they never had, and flags for a
  human that `ceiling_check_total{result="failed_open"}` **is** SC3's "failed-open counter".
- **CL-11's disposition is stated rather than left silent**, in `03-CONTEXT.md` and again in `03-02`,
  without splitting or remapping a stable requirement id. That is the instruction followed exactly.
- **The `prope_report` checkpoint (`03-05` Task 3) is the right posture even if the adoption is
  arguable.** Both readings of whether a database role falls inside AC-10 are written out, the refused
  third option ("do nothing and mention it nowhere") is named, and the exposure is asserted by a test
  rather than described. Whichever way a human rules, the record distinguishes *considered* from
  *unnoticed*.

---

## Findings

### 1. `03-05-PLAN.md` Task 1 — the layer-2 exemption list names a type that does not exist and is short by at least two entries, while the plan's own prohibition forbids growing it

**Severity: blocker.**

**Authority:** `docs/modules/call-ledger.lock.yml` `acceptance_criteria` AC-10 ("the module's entire HTTP
**and internal** surface"), ROADMAP SC4, requirement **CL-10** — the requirement this plan owns.

**What the plan says.** Task 1: *"`CallBodyDraft` legitimately names `request_body`, `response_body` and
`byte_size` — it is the **write-side input** type… So does `CallBodyPayload` on the envelope"*, followed
by `BODY_NAMING_EXEMPTIONS` with *"these are the two types that name it"* and an assertion on
`len(BODY_NAMING_EXEMPTIONS)`. The plan's prohibition list then states: *"MUST NOT grow the internal
walk's exemption list to make a failure go away."*

**What the code actually contains.**

- `src/prope/call_ledger/envelope.py:68` declares **`CallRecordPayload`**, not `CallBodyPayload`. There
  is no type named `CallBodyPayload` anywhere in `src/`. The exemption list as written names a
  nonexistent symbol.
- `CallRecordPayload` declares `request_body`, `response_body` and `byte_size` at `envelope.py:120-122`.
- `CallRecordEnvelope` declares **`payload: CallRecordPayload`** at `envelope.py:166`, and `payload` is a
  member of `FORBIDDEN_FIELD_NAMES` (`tests/architecture/test_route_table.py:78`).
- `CallRecordDraft` declares **`body: CallBodyDraft | None`** at `domain.py:160`, and `body` is also a
  member of `FORBIDDEN_FIELD_NAMES` (`test_route_table.py:76`). `03-01` itself depends on this field
  existing — *"rebuilds it metadata-only with `dataclasses.replace(draft, body=None)`"*.

So the walk as specified produces **at least four** offenders, not two. An executor following this plan
literally is caught between a `len()` assertion pinned at two, a symbol that does not resolve, and a
prohibition against growing the list — and the three available escapes are all wrong: narrow
`FORBIDDEN_FIELD_NAMES` (breaks the layer-1 assertion that already uses it and is forbidden by the
plan's own "import it, do not re-declare it" link), restrict the walk to non-write-side modules (makes
it vacuous and defeats the discovery requirement), or grow the list silently (the prohibition).

**Why it matters.** CL-10 is the one requirement in this phase whose whole value is that the assertion is
non-vacuous. A layer-2 walk that is quietly narrowed to pass is worse than no layer 2 at all, because
Phase 23 will extend it believing it means something.

**Fix.** Replace the two-entry list with the real set, enumerated from the code, each entry carrying its
own reason and the rule restated as *write-side input and transport types*:
`prope.call_ledger.domain.CallBodyDraft` (the body a caller hands in),
`prope.call_ledger.domain.CallRecordDraft` (holds the draft body by composition — field `body`),
`prope.call_ledger.envelope.CallRecordPayload` (the body on the wire),
`prope.call_ledger.envelope.CallRecordEnvelope` (field `payload`, the transport wrapper). Assert
`len(...) == 4`. Then keep the plan's positive control and strengthen it: the direction that matters is
that **no type on the read side** — `RunTotals`, `CeilingDecision`, `WriteResult`, `EvalUsageRow`, and
every public return annotation — names one, which is the assertion AC-10 is actually about. Correct
`CallBodyPayload` → `CallRecordPayload` wherever it appears in the plan.

---

### 2. `03-04-PLAN.md` Task 1 — `/metrics` is served as an eighth path with no declared deviation against `apis.exposes`, and `interfaces.md` says in as many words that the line is owed

**Severity: major.**

**Authority:** `docs/modules/call-ledger.lock.yml` `apis.exposes` (five `/api/v1` routes, `/healthz`,
`/readyz` — `/metrics` is absent); `docs/architecture/interfaces.md:1236-1239`; ORCHESTRATION §5
(*"Do not expose an API or event outside its `apis.exposes[]`"* … *"If one of those turns out to be
necessary, that is real information — the spec is wrong. Stop, write
`docs/brainstorm/open_questions/OQ-NNN.md` naming the exact lock-file or interfaces field"*).

**What the plan does.** Adds `GET /metrics` as a plain `APIRoute` on `app`, grows `EXPECTED_ROUTES` from
seven to eight and `UNVERSIONED` from two to three, and raises `OQ-023` (label cardinality) and `OQ-026`
(two registries). **Neither open question names `apis.exposes`**, and neither cites `interfaces.md`'s own
note about it.

**Why it matters, and why this is a declaration defect rather than a design defect.** The route itself is
almost certainly correct: ADR-0052's Caddyfile already routes `handle /metrics { reverse_proxy
app:8000 }`, and `interfaces.md:1236-1239` states plainly — *"`/metrics` is declared in no lock file's
`apis` block, so registering it would be inventing a seam into existence. It is a real surface … and it
**should gain an `exposes` line during step 6** rather than an INT invented here."* Step 6 ran, flipped
`ready_for_build: true`, and **did not add the line.** That is precisely the class of omission
ORCHESTRATION §5 exists for: an authority acknowledges the surface, prescribes the remedy, and the sweep
missed it. Phase 3 is the first phase to hit it and is therefore the phase that owes the declaration.
Shipping the eighth path with three open questions raised and *this* one unraised is absorbing a known
spec gap silently — the one behaviour the standing contract forbids by name.

There is a second, smaller edge on the same route worth carrying in the same clause: `03-04` adds
`/metrics` to `UNVERSIONED`, which is the set of routes asserted to declare **no** `ManagementAction`.
Access-control's AC-10 (*"Every route in every module declares an action from the vocabulary; a route
declaring none fails the test rather than defaulting to unauthenticated"*) is a Phase 7/9 requirement
that will meet this exemption set. Enlarging it from two to three is a decision that should be visible to
that phase, not discovered by it.

**Fix.** Add a clause to `OQ-026` (it is already the metrics-exposition question, `severity: high`, and
`03-04` already owns it) naming **`docs/modules/call-ledger.lock.yml` `apis.exposes`** as the field, quoting
`interfaces.md:1236-1239`'s "should gain an `exposes` line during step 6", and recording that this phase
ships the surface ADR-0052 already routes while the `exposes` line remains owed. Add one sentence naming
the third `UNVERSIONED` entry as an input to access-control AC-10 in Phase 7/9. No new OQ id is needed
and none is available — the range is fully consumed.

---

### 3. `03-01-PLAN.md` Task 1 and Task 2 — under both of SC1's provocations, `publish_failed_total` never moves, so the lock's declared detection for the failure mode this phase is about cannot fire

**Severity: major.**

**Authority:** `docs/modules/call-ledger.lock.yml` `failure_modes` row 2 (the replacement scenario) —
*"Detection: `prope_call_ledger_publish_failed_total` rising, `LedgerPublishFailing` (ticket), and
`prope_call_ledger_fallback_direct_write_total` rising **in the same window**"* — and
`observability_requirements.alerts` `LedgerPublishFailing`. The ROADMAP Spec line names `failure_modes`
(**all 8 rows**) and `alerts`.

**The mechanism.** `publish_failed_total`'s label set is closed at three (`unroutable | nacked |
timeout`), and `03-01`'s prohibition list keeps it closed: *"MUST NOT add a fourth value to
`prope_call_ledger_publish_failed_total`'s reason label; the bare-exception branch counts a drop and a
fallback, never a fourth reason."* That matches the code: `enqueue.py`'s `except Exception` branch
(a closed channel, a dead connection, a broker that was never running) deliberately leaves
`publish_failed_total` untouched, with the reason written in the comment.

Now trace the phase's own two SC1 provocations:

- **Closed channel under a running publisher** (`03-01` Task 2, provocation 1, the 1,000-record test):
  `exchange.publish` on a closed channel raises an aio-pika channel-state error, not `DeliveryError` and
  not `TimeoutError` — so it lands in the bare-`except` branch. `publish_failed_total` stays at zero for
  all 1,000 records.
- **Broker unreachable at startup** (Task 1's adopted `fallback-only-job`): `publish_record` is never
  called at all. `publish_failed_total` stays at zero for the life of the process.

So in the exact scenario ADR-0041 was written about — *"`docker compose up -d` restarting the broker
while `app` keeps serving"*, which `03-01` Task 1 itself calls "the mundane one" — the declared
detection narrative is half-dead and `LedgerPublishFailing` is silent. The only rising series is
`fallback_direct_write_total`. `03-04` Task 4 then writes `LedgerPublishFailing` into the rules file with
`expr` subject *"`publish_failed_total` rising"* and a description that does not mention this, so the
rules file ships an alert the phase's own tests prove cannot fire on the ordinary outage.

**Why it matters.** The asymmetry is visible inside the plan set itself: `03-01` accepts introducing a
**third** `reason` value on `body_dropped_total` (`fallback`) against a declared two-value set, raises
`OQ-022` for it, and is right to. It then refuses the equivalent move on `publish_failed_total` and
raises nothing — so one declared label set is extended-and-declared and the other is left with a
detection gap that is neither closed nor recorded.

**Fix.** Pick one and write it down; do not leave it implicit.

- **Preferred:** in `03-04` Task 4, make `LedgerPublishFailing`'s `expr` subject
  `fallback_direct_write_total` rising **or** `publish_failed_total` rising, and say in the
  `annotations.description` why: the three declared reasons cover a broker that answered and refused,
  while a broker that is absent produces no confirm at all and is visible only on the fallback counter.
  Add that as a fifth clause to `OQ-022` (which already blocks
  `observability_requirements.metrics`), naming `failure_modes` row 2's detection line and the
  `LedgerPublishFailing` alert as the fields in conflict.
- **Or:** extend `publish_failed_total`'s `reason` set with a fourth value (`unavailable`) exactly the way
  `body_dropped_total` gained `fallback`, drop the prohibition, and raise the same OQ clause. Either is
  defensible; silence is not.

---

### 4. `03-02-PLAN.md` Task 2 — `redelivered_total` is asserted in a test whose consumer is not the drain, so the increment site the plan just built is never reached

**Severity: major.**

**Authority:** ROADMAP SC2 (*"every redelivery is counted"*); `docs/modules/call-ledger.lock.yml`
`observability_requirements.metrics` `prope_call_ledger_redelivered_total`; PITFALLS §2's restated AC-2.

**What the plan says.** Task 2 puts the increment in the drain's `_parse`, then: *"Its existing
redelivery test (`:199-244`) already stops a consumer with messages unacknowledged, drops the connection,
and asserts `message.redelivered` on the second consumer's deliveries — it is the right mechanism and the
right place. **Grow it to assert `redelivered_total` moved by the number re-sent.**"*

**What that test actually is.** `tests/broker/test_drain_failure_classification.py:199-244`
(`test_unacknowledged_messages_are_redelivered_after_a_consumer_restart`) builds two **raw** consumers —
`connection.channel()`, `queue.iterator()`, `message.ack()` — and never runs `run_drain`, never calls
`_parse`, and never opens a database transaction. `redelivered_total` is incremented inside `_parse`. A
raw `queue.iterator()` cannot move a counter that lives in the drain, so the added assertion fails as
written, and the likely executor response is to relax it to "moved by ≥ 0", to move the counter out of
`_parse`, or to silently rewrite the test into something the plan did not specify.

**Why it matters.** This is one of SC2's two named counters, and the failure mode is the worst kind — the
assertion looks like it proves the increment site and does not touch it.

**Fix.** State explicitly in Task 2 that the second consumer must be **the drain** (via
`_helpers.drain_until`, the existing harness), not a raw iterator: publish, consume-without-ack on a raw
consumer to force the unacked state, drop the connection, then let the **drain** take the redelivery and
assert `redelivered_total` moved by the number re-sent. Keep the existing raw-consumer test unchanged as
the broker-behaviour assertion it already is, and add the drain-side one beside it rather than growing
the wrong test.

---

### 5. `03-02-PLAN.md` Task 3, mechanism 2 — the real-redelivery test as specified cannot exercise the upsert, because nothing writes the records before they are redelivered

**Severity: major.**

**Authority:** ROADMAP SC2 (*"Every message redelivered after an unacknowledged consumer restart lands
exactly once; the workspace's monthly total is unchanged"*); PITFALLS §2's restated AC-2 (*"including
records the fallback already wrote directly … the workspace's monthly spend total is unchanged, and
`duplicate_call_id_total` accounts for every redelivery"*).

**What the plan says.** *"Use the existing mechanism: consume without acking, drop the connection,
consume again, assert `redelivered_total` moved and — the half that makes it an SC2 test rather than a
broker test — that the workspace total is still unchanged and the DLQ is still empty after the
redelivered messages have been written."*

**Why it does not prove SC2.** "Unchanged" needs a prior state to be unchanged **from**. In the existing
mechanism the first consumer acknowledges nothing and writes nothing, so at the moment of redelivery no
row exists, no `workspace_spend` figure exists, and the redelivered messages are simply first
deliveries with a `redelivered` flag set. The upsert never sees a conflict, `duplicate_call_id_total`
never moves, and "lands exactly once" is satisfied by a code path with no idempotency in it at all. The
test passes today, before Task 1's change, which is the definition of an assertion that cannot fail.

The scenario SC2 actually names is the dangerous one: **the drain committed the transaction and died
before acknowledging.** That is the shape at-least-once delivery produces routinely, it is the one
`failure_modes` row 3 describes, and it is the only one where the returned-`call_id` aggregate is
load-bearing.

**Fix.** Specify the ordering in the plan rather than leaving it to the executor: drive the drain until N
rows are committed in `ledger.call_record` and the `workspace_spend` row is readable through
`migrate_engine`, **then** drop the connection before the acks land (the existing `drain_until` harness
already owns the stop signal), then let a second drain take the redelivery. Assert all four in one test:
row count still N, `workspace_spend.call_count` and `total_cost` byte-identical to the snapshot,
`duplicate_call_id_total` moved by exactly the number redelivered, and the DLQ empty. If forcing a
commit-before-ack proves impractical against aio-pika's ack timing, say so in the plan and name the
re-publish test as the one that carries the idempotency claim — but do not leave two tests where the
reader believes the second proves something the first does not.

---

### 6. `03-06-PLAN.md` — AC-12's write-lag clause is dropped, and the plan says so on purpose

**Severity: major.**

**Authority:** `docs/modules/call-ledger.lock.yml` `acceptance_criteria` **AC-12**: *"Given 50 rps
sustained for 10 minutes, when enqueue is measured in the caller's process, then p95 stays under 1 ms,
**write lag p95 stays under 2 s**, and no metadata is dropped."* `.planning/REQUIREMENTS.md`'s
traceability table maps **CL-12 → call-ledger AC-12**. The ROADMAP Spec line names `acceptance_criteria`.

**What the plan says.** Objective: *"It does not measure the drain, the fallback, or `write_lag_seconds`
— those are the *system's* lag and belong to the metric plan 03-01 defined and plan 03-02 observes.
CL-12 is about the **caller's** span only."*

**Why the reasoning is half right and the outcome is still a gap.** ROADMAP SC5 omits write lag, so the
success criterion is met. But CL-12's acceptance criterion of record is AC-12, and AC-12 has three
clauses. AC-12 is **not** in PITFALLS §2's restatement table, so there is no exemption to claim: its text
stands as written. `03-02` observes `write_lag_seconds` and asserts only that observations exist and none
is negative; nothing anywhere asserts the 2-second p95. Milestone M1 closes with this phase, so if it is
not asserted here it is asserted by nobody.

The instrumentation is already in place — `03-01` chose `WRITE_LAG_BUCKETS` with `2.0` as an edge
*specifically* so this quantile is computable, and the bucket comment cites `performance_requirements`'
p95 < 2 s. The measurement exists; only the assertion is missing.

**Fix.** Add the third clause to `03-06` Task 2's full-fat test — after the 30,000 rows land, read
`prope_call_ledger_write_lag_seconds`' bucket counts from the registry and assert that at least 95% of
observations fall at or below the `2.0` edge, reading `2.0` from `WRITE_LAG_BUCKETS` rather than as a
literal (the same discipline Task 3 already applies to `0.001`). If cross-process registries make that
unreadable from the test process, say **that** in the plan and route the clause explicitly — an
unassertable clause named and routed is a different artifact from one deleted in an objective paragraph.

---

### 7. No plan owns `test_plan.load`'s drain-throughput and stall-recovery clauses, and `deferred-items.md` does not route them forward

**Severity: major.**

**Authority:** `docs/modules/call-ledger.lock.yml` `test_plan.load`: *"50 rps sustained for 10 minutes
with bodies attached; enqueue p95 < 1 ms measured in the caller; write lag p95 < 2 s; **writer drain >=
500/sec**; then **stall the writer for 60 s and assert the backlog clears rather than growing**, since a
writer that only just keeps up never recovers from a stall."* Reinforced by `performance_requirements`
rows 2 and 7 (*"broker backlog drain after a consumer restart — drained within 60 s"*), both of which
`03-CONTEXT.md`'s canonical-refs block names explicitly. The ROADMAP Spec line names `test_plan`
including `load`.

**What the plan set contains.** `03-06` covers the enqueue p95 and the zero-drop claim, twice. A grep
across all six plans, `COVERAGE.md` and `deferred-items.md` for `500/sec`, `records/sec` and
"backlog clears" returns nothing but `03-04`'s unrelated depth-gauge prose. The drain throughput target
and the stall-and-recover test are in **no** plan, in **no** deferred item, and in **no** routed-to-a-later-phase
note.

**Why it matters.** `performance_requirements` states the reason itself, and it is not a rounding
concern: *"a writer that merely keeps up has no capacity to clear a backlog after a stall, so every stall
becomes permanent pressure."* This phase builds the fallback whose entire purpose is to absorb a broker
outage — after which there is a backlog to clear. M1 closes here; an unowned, unrouted lock-file test
clause becomes invisible the moment this phase is marked done.

**Fix.** Either add a third case to `03-06` Task 2's already-marked, already-container-bound full-fat
run — pause the drain for 60 s mid-run, resume, and assert `ledger.call_record` reaches 30,000 (the
durable side, per the plan's own "the gauge is a graph; the table is the fact" rule) within the stated
window, deriving the ≥500 rec/sec figure from rows-written / elapsed across the recovery — or record both
clauses in `deferred-items.md` with a named owning phase and the reason this phase cannot carry them.
The second is acceptable; silence is not, and it is the option ORCHESTRATION §9.4 was written to prevent.

---

### 8. `03-01-PLAN.md` Task 2 / `03-CONTEXT.md` D-41 — `occurred_at` is described as crossing no registered contract, and INT-018 registers it

**Severity: minor.**

**Authority:** `docs/architecture/interfaces.md:667` — *"**Envelope carries** (A-142 §5):
`schema_version`, `call_id`, `workspace_id`, **`occurred_at`**, `producer`."*

**What the plan says.** D-41, repeated in `03-01`: *"`occurred_at` is call-ledger's own envelope field and
crosses no registered contract, so nothing outside this module changes."*

**Why it is wrong as written, and why it is still minor.** `occurred_at` is a named field of INT-018's
registered envelope. Moving the stamp from `publish_record` into `enqueue()` changes nothing structural —
the field's presence, name and type are identical, A-142's additive-only evolution rule is untouched, and
call-ledger owns both producer and consumer today. What changes is the **semantic**: the value becomes
"when the caller handed the record over" rather than "when the publisher published it". The gateway
inherits that meaning in Phases 19–21 without ever having been told, and INT-018 is named in
`interfaces.md`'s own residual-risk block as *"the only shape in Prope that can be in flight across a
deploy"*.

**Fix.** Change the sentence in `03-01` Task 2 from "crosses no registered contract" to the accurate
form — INT-018 registers the field; its shape is unchanged and its sampling point moves — and require
the new `enqueue()` docstring paragraph to state the meaning a future gateway will inherit, in the same
sentence that records the third sanctioned clock read.

---

### 9. `test_plan.chaos` rows 4 and 5 are neither planned nor raised as stale

**Severity: minor.**

**Authority:** `docs/modules/call-ledger.lock.yml` `test_plan.chaos`: five clauses. The ROADMAP Spec line
names `test_plan` including `chaos`.

**Disposition of the five, as the plans leave them.** Clause 1 (kill mid-write, exactly-once on replay) —
covered in substance by `03-02` Task 3 subject to finding 5. Clause 2 (fill the spill volume) — correctly
raised as stale in `OQ-024`. Clause 3 (saturate the body lane with oversize bodies, ordinary metadata
unaffected) — covered by `03-01` Task 3. **Clause 4** (*"break the retention job's predicate and assert
the alert fires on data age rather than on job status"*) — `03-04` Task 3 asserts the gauge reads the
data and reads the larger of two ages, but never provokes a sweep that runs cleanly and deletes nothing,
which is the exact failure `failure_modes` row 6 and `LedgerRetentionOverdue` exist for. **Clause 5**
(*"run the deletion job concurrently with peak writes and assert the writer's lag stays inside its
target"*) — absent from every plan and from `deferred-items.md`.

**Fix.** Add one case to `03-04` Task 3 for clause 4 — seed a body older than the window, run the sweep
with a predicate that matches nothing, assert the sweep reports success **and** the gauge reads above the
window — which is cheap, since the fixture is already being built for the three cases the task has.
Record clause 5 in `deferred-items.md` with a named owner, alongside finding 7's items.

---

### 10. `03-06-PLAN.md` — SC5's proof lives behind an environment variable, and the plan's verification block does not tell the verifier to set it

**Severity: minor.**

**Authority:** ORCHESTRATION §9.1 — *"Every ROADMAP success criterion for the phase is proven by a test
the **verifier ran itself** in its own session — not by reading a SUMMARY."*

**The gap.** The split in `03-06` is well argued and the adopted posture (skip, do not deselect) is right.
But the artifact it produces is a phase whose SC5 test is skipped by `uv run pytest -q`, with the
observed numbers recorded in `03-06-SUMMARY.md` by the executor. §9.1 explicitly forbids the verifier
scoring a criterion from a SUMMARY. The plan's `<verification>` block says the executor ran it once; it
never instructs the verifier to run it.

**Fix.** Add one line to `03-06`'s `<verification>` block, in the imperative the other entries use:
*"The verifier runs `PROPE_RUN_LOAD=1 uv run pytest -m load -q` in its own session — ORCHESTRATION §9.1
does not permit SC5 to be scored from this plan's SUMMARY."* Carry the same line into
`deferred-items.md` beside item 6, so the ten-minute cost is on the phase's timeline rather than a
surprise at verification.

---

## Not findings — checked and dismissed

Recorded so the next reader does not re-open them.

- **`deploy/prometheus/rules/call_ledger.rules.yml` as a new top-level directory.** It is a repository
  artifact, not a service; PITFALLS §4 gives the deployment stack no milestone, and `03-04` states the
  boundary of what its test can claim (well-formed YAML plus real metric names, never `promtool check
  rules`). Correct.
- **Shipping `/metrics` while ADR-0030 rejects *"a `/metrics` endpoint with nothing scraping it"*.** That
  rejection is of the endpoint **as a substitute for** the Prometheus + Grafana stack, not of the endpoint
  the chosen option requires. `OQ-026` records the missing scraper as its fourth rejected answer. No
  contradiction.
- **`ledger.workspace_retention` outside `data.owns`.** Inherited from Phase 2's `OQ-018`, correctly cited
  and not re-raised.
- **T-005's queue-argument read-back.** Already discharged in Phase 2 —
  `tests/broker/test_declared_arguments.py:119-128` asserts `x-max-length` and
  `x-overflow: reject-publish-dlx`, and `src/prope/broker/topology.py:83-88` carries the
  dead-letters-rather-than-drops argument. Phase 3 correctly owns only the `dlq_depth` half.
- **D-30's removal of the two dead-letter `metadata_dropped_total` increments.** ADR-0041's text supports
  it, the substitute signal and its 30-day-TTL limitation are written at the removal site, and the change
  in an existing page's meaning is on the human list. Right, including the part most likely to be skipped
  — that it is a removal.
- **`MAX_RETENTION_DAYS = 3650` and `MAX_BODY_BYTES = 256 KiB`.** Both argued from stated figures
  (`timedelta` overflow, ADR-0033's "roughly 10 KB per call" and the 24-hour TTL), both product-visible,
  both on the human list. Neither is round-picked.

---

VERDICT: 1 blocker / 6 major / 3 minor

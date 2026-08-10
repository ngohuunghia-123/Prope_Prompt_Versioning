# ADR-0046 — The admission gate is two per-process caps, because the processes are the priority classes

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: provider-access — supersedes ADR-0016's mechanism, not its intent
**Related**: A-012, A-031, A-043, A-054, A-062, A-063, A-084, A-088, A-093, A-129, A-130, A-134,
ADR-0016, ADR-0026, ADR-0028, ADR-0033, OQ-012

## Context

ADR-0016 exists to stop one thing, stated in this module's own risk table: *"a five-suite eval
submission collides with live gateway traffic"*, so that *"the developer persona experiences an eval run
as a production incident — the exact veto positioning.md §11 warns about."* Its mechanism is named
precisely: **"a per-configuration semaphore with a reserved share, not a scheduler"**, sized
`max_concurrency` (default 32) with `reserved_interactive` at `max(4, 25%)`. Batch occupies at most the
difference; interactive never queues behind batch and fails fast rather than waiting.

A semaphore is a process-local object, and when ADR-0016 was written A-012 said there was one process.

**ADR-0028 changed that during Stage 1 and nothing reconciled the two.** It added a `worker` service —
the same image, a different command — and A-054 is already flagged for rewrite because evaluation's
*"in-process at concurrency 5"* is no longer the shape. Once eval dispatch runs in `worker` and the
gateway runs in `app`, the two priority classes no longer share the object through which one is supposed
to yield to the other:

- `max_concurrency: 32` becomes **64 in flight against a single provider key**, since each process
  holds its own semaphore initialised to the same number from the same column.
- `reserved_interactive` reserves nothing from anyone. There is no batch dispatch in the `app` process
  to hold slots back from, and the `worker` process has no interactive dispatch to reserve for.
- Every guarantee in the performance table — *"an interactive dispatch never queues behind a batch
  dispatch"* — is true, but for the wrong reason and only by accident of topology.

## Decision

**`provider_config.max_concurrency` and `reserved_interactive` are replaced by
`interactive_concurrency` and `batch_concurrency`. Each process holds a plain local semaphore over the
column that belongs to it: `app` over the first, `worker` over the second. Their sum is the budget
against the provider key.**

- **The processes are now the priority classes.** `app` dispatches only interactive traffic and `worker`
  only batch, so *"batch yields to interactive"* stops being something a semaphore enforces and becomes
  something the deployment topology makes structurally true.
- **This is a stronger guarantee than the semaphore gave, not a weaker one.** A semaphore could only
  stop a batch dispatch taking a *slot*. It never stopped batch work consuming event-loop time, CPU,
  TLS handshakes, or connection-pool entries in the same process — all of which land inside the
  gateway's p95 and none of which the gate could see. A-130 records the same class of coupling for
  argon2id and ~~Jinja rendering~~. Separate containers remove all of it at once.
  *(Amended 2026-08-09 — **ADR-0052 moves rendering to the browser**, so Jinja is no longer in `app` and
  this list is argon2id alone. The argument for separate containers is unchanged in kind and one item
  weaker in weight; see A-130.)*
- **Admission stays free on the hot path.** A local `asyncio.Semaphore` acquire keeps the performance
  table's *"admission wait p95 < 1 ms"* trivially true, and the interactive path still fails fast rather
  than queueing, because on the hot path a queue is a slower error.
- Defaults are `interactive_concurrency: 24` and `batch_concurrency: 8`, recorded as a placeholder in
  **A-134** — no real provider rate-limit figure exists, and OQ-012 has not supplied a load number
  either. They are sized so the sum stays at ADR-0016's original 32.
- **This depends on evaluation's pass landing batch dispatch in `worker`.** A-054's rewrite is where
  that is confirmed. If evaluation decides otherwise, this ADR is re-opened with it, and that dependency
  is recorded in both locks rather than assumed.
- ADR-0016's *intent* is unchanged and its ADR stays accepted: one key, two classes of traffic, batch
  yields. Only the mechanism is superseded.

## Alternatives rejected

**Coordinate slots through PostgreSQL** — an advisory lock or a slots table, so the budget is genuinely
global across both processes. This is the only option that preserves ADR-0016's stated feature, that
*"the reserved share is a floor rather than a cap so an idle gateway leaves the whole budget to batch."*
Losing that is the real cost of this decision and it is not dismissed. It was rejected on where the cost
lands: a database round trip **before every dispatch, on the interactive path**, inside a 10 ms
overhead budget that is itself a share of the gateway's 50 ms. The performance table says an interactive
dispatch must never queue; this would make it wait on the same database whose latency is already the
system's dominant hard dependency. It is also a distributed semaphore with crash-release semantics —
a component with a runbook, which A-012 has priced as expensive every time it has come up.

**Route all dispatch through the `app` process**, with `worker` calling it over HTTP so one semaphore
sees everything and ADR-0016 needs no change. Rejected on two counts, either sufficient. It puts batch
eval load directly into the process serving the gateway's budget, which is the exact coupling A-130 was
written to warn about, and it makes `app` the throughput ceiling for eval runs. And it adds an internal
hop that carries credential-bearing requests and relays every stream chunk twice, against a per-chunk
overhead budget of 1 ms.

**Leave ADR-0016 as written and accept the doubled budget.** Rejected because it is not a decision, it
is the current state — and its failure mode is the one the module is least able to detect. The provider
returns 429s, `origin` is labelled `provider`, and `ProviderInteractiveShed` never fires because Prope's
own ceiling was never reached. Prope would be causing the rate limiting it reports as the provider's.

## Consequences

- **`ProviderInteractiveShed` gets sharper.** It previously had to be read as *"either Prope's ceiling
  is too low or batch ate the slots"*; under separate processes only the first is possible, so the alert
  now names its own cause. `ProviderBatchStarved` correspondingly means the batch cap is too low, and
  nothing else.
- **The floor-not-cap property is lost, and that is the price.** An idle gateway no longer donates its
  slots to a running eval suite, so a large submission takes longer than the hardware could manage.
  ADR-0016 already chose this direction of the trade explicitly — *"this is the designed direction"* —
  and A-063's global per-workspace bound still sits above both caps unchanged.
- Two knobs instead of one, and they must be set as a **sum**: the provider sees one key and does not
  care which container a request came from. A-134 carries the numbers and the revisit trigger.
- **AC-6 must be restated.** It reads *"given a configuration with max_concurrency 8 and
  reserved_interactive 4, when 20 batch dispatches are in flight, then an arriving interactive dispatch
  is admitted without waiting"* — a single-process assertion against columns that no longer exist. The
  replacement asserts the two caps hold independently in their own processes and that their sum is never
  exceeded upstream. Recorded as owed to the step-6 sweep.
- A third dispatching process would break this the same way ADR-0028 broke ADR-0016, and the mitigation
  is the same one: the cap columns are per-process by name, so adding a process means adding a column
  and noticing.

> **Dependency confirmed 2026-08-09 by ADR-0049, one pass later.** The clause above — *"This depends on
> evaluation's pass landing batch dispatch in `worker`. … If evaluation decides otherwise, this ADR is
> re-opened with it"* — was the right thing to write down, and it resolved in this ADR's favour. The eval
> executor is a claim loop in `worker`; `app` dispatches interactive traffic and nothing else. *"The
> processes are now the priority classes"* holds as written, and this ADR is confirmed rather than
> reopened.
>
> **A-063 shrank in the same pass, and it shrank because of this ADR.** Its *"at most 10 across all runs
> of one workspace"* clause was written when it sat conceptually above the provider seam; once the eval
> executor moved into `worker`, that clause and `batch_concurrency: 8` were two dispatch-level semaphores
> in one process, with the tighter one always binding — the ADR-0016 defect, rebuilt by accident. The
> clause is deleted. `batch_concurrency` is now the **only** dispatch-level bound on eval traffic, which
> makes A-134's placeholder numbers load-bearing for evaluation's 120 s Success target as well as for
> the provider key.
>
> **One asymmetry surfaced that is worth carrying into any conversation about scaling `worker`.**
> ADR-0049's surviving bound is a **database predicate inside the claim transaction**, so it stays
> correct under a replicated `worker`. This ADR's caps are process-local `asyncio.Semaphore` objects and
> do not — two `worker` replicas double `batch_concurrency` against one provider key, which is precisely
> how ADR-0028 broke ADR-0016. **A `worker` replica and a cross-process cap are the same conversation,
> and the cap has to come first.** A-138 records it.

> **The "third dispatching process" warning has a named candidate, 2026-08-09, from the gateway's pass.**
> The final consequence above reads: *"A third dispatching process would break this the same way
> ADR-0028 broke ADR-0016, and the mitigation is the same one: the cap columns are per-process by name,
> so adding a process means adding a column and noticing."* That is now concrete rather than
> hypothetical.
>
> **A-130 proposes splitting the gateway out of `app` into its own container**, with a load-test
> trigger. If that is taken, interactive dispatch moves with it — but **`app` keeps dispatching**,
> because A-090's provider **verification probe** calls upstream when a provider configuration is
> registered, and that is a management action. So the split leaves the probe uncapped or needs a third
> column. The noticing this ADR relied on happened: it was found while filling the gateway's deployment
> row, not after the split.
>
> A-130 is amended with the corrected price and the gateway's pass confirmed it in place, so nothing
> changes here today. **The ordering is what matters**: the third column, or moving the probe to
> `worker`, is decided *before* the split, not discovered by a doubled budget against a provider key
> afterwards. The tidiest end state — probe in `worker`, gateway with its own container, `app`
> dispatching nothing — was presented and not taken, because it makes provider registration
> asynchronous to serve a latency budget A-031 still calls a placeholder.

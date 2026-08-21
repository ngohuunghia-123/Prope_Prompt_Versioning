# ADR-0018 — The call-record body store has no read path in the MVP

**Status**: Superseded by ADR-0059 (2026-08-20)
**Date**: 2026-08-08
**Decision**: agent (A-105, A-106)
**Module**: call-ledger (written while locking call-ledger)
**Related**: A-020, A-037, A-039, A-040, A-044, A-046, OQ-013, OQ-006

## Context

> Historical decision. ADR-0059 replaces the absolute no-read rule with one opt-in, role-gated,
> server-redacted and audited prompt-scoped read path. The dependency argument below remains active:
> prompt-registry authorises before invoking a narrow call-ledger seam.

The module map gives call-ledger `deps_out: none` and states the forbidden edge as
"**call-ledger → anything**", on the grounds that a ledger which calls back into a module serving a
request is how "log after" becomes "log during".

Follow that to its consequence and something falls out that the map does not say: with no edge to
access-control, **this module cannot check a permission**. So any API it exposes must be one that
needs no check.

That collides with A-040, which assumes bodies are "readable by the prompt's owner or an explicit
`read_bodies` permission". A-040 describes a capability, and nothing in the MVP has a surface for it.
Checking the readers: the gateway is forbidden the read direction, evaluation reads only its own run's
priced totals, release-control has no edge here at all, and prompt-registry has none either. Nobody
reads a body.

Meanwhile `00_context.md#scope` already puts "trace and span models, a trace explorer UI, analytics
dashboards" out of scope, and OQ-013 — rated **Critical** in `business-analysis.md` §11 — is open on
exactly the four questions a reader would need answered first: retention, who may read, PII and
redaction, residency.

## Decision

**Bodies are written and deleted. Nothing reads them in the MVP.**

- No endpoint, no export, no admin viewer, no debug route, and no join from another module's query.
- `call_body` is a separate table from `call_record` so the write path, the drop policy, the retention
  policy, and the (absent) read policy can differ.
- The absence is asserted as a test against the route table itself (AC-10), not left as an
  understanding — so a new endpoint cannot quietly add one.
- Retention is a per-workspace setting from day one with A-040's 30 days as the default, deletion is a
  real delete, and the alert measures the age of the oldest surviving body rather than whether the job
  ran (A-106).
- Metadata is unaffected. It is kept indefinitely, it has readers, and it is the audit trail NFR-02
  requires.

The store is therefore write-then-delete until OQ-013 is answered and a later release builds the
reader deliberately, with the policy already decided.

## Alternatives rejected

**Build the viewer now — it is a table and a template.** Rejected, and it is the tempting one because
it genuinely is easy. What it is not is cheap: it turns OQ-013 from a question that blocks the pilot
into a question that blocks the build, because the moment a body is readable, "by whom" must have an
answer. It would also require adding call-ledger → access-control, which ends this module's status as
a sink and reopens the p95 argument the forbidden edge settled.

**Let call-ledger check permissions itself, with its own copy of the rules.** Rejected outright. Two
implementations of "who may see this" is the failure the map already avoided three times over
(A-044's no-standalone-UI rule for property-history is the same shape), and the copy that drifts is
always the one nobody is looking at. It also puts an authorisation decision in the module least able
to explain it — this one holds no actor model at all.

**Add the edge to access-control anyway, on the argument that a read-path check is not on the response
path.** Rejected on where it leads rather than on what it costs today. The edge would be defensible
for one read API and then available for the next thing, and "call-ledger → anything" exists as a
blanket rule precisely because the first exception is always reasonable. If a reader is built later,
adding the edge then is an explicit decision with a written reason; adding it now is a decision nobody
records.

**Store bodies encrypted with a per-workspace key so a reader is safe by construction.** Rejected as
solving a different problem. The open questions in OQ-013 are retention, standing to read, PII
handling, and residency — encryption at rest addresses none of them, and it would make the deletion
job harder while creating a second key hierarchy beside ADR-0014's.

**Do not store bodies at all until the policy exists.** Rejected because the user already decided the
other way, explicitly: "Prope còn lưu lại lịch sử request/response, sử dụng cho mục đích truy xuất, cải
tiến sau này". Storing is settled; the policy is what is open. This ADR narrows the exposure without
reversing the decision.

## Consequences

- OQ-013's access half now concerns a surface that does not exist, which is a much better position to
  answer it from — the answer becomes the design of a new reader rather than a retrofit onto one
  already in use.
- A-040's `read_bodies` permission is deferred, not deleted. It remains the right shape for whenever a
  reader is built.
- The Langfuse export A-039 anticipates is a *reader*, and it is out of scope for the same reason.
  When it is built it will be the first thing to need this decision revisited, and it should come with
  OQ-013's answer in hand.
- The riskiest data in Prope has the fewest ways to reach it, and that is now a property of the
  architecture rather than of the current absence of a feature request.
- A-020 keeps doing the heavy lifting until OQ-013 is answered: no real corporate prompts, therefore
  no real end-user content, until the baseline is signed off.

# Step 10 — draft angle plan

Three sub-orchestrators, three genuinely different analytical angles on the SAME 12-section
contract. Not three summaries of the same argument — three defensible readings that a
synthesizer can arbitrate between. Each must produce the full 12 sections; the angle governs
what each section *argues*, not which sections exist.

## The spine all three share

The register is only as good as the fields it can populate without asking anyone to maintain
them. Ingestion populates it from the existing mess; distribution keeps usage and cost live;
the promote gate attaches evidence and captures the judgment that cannot be auto-derived.
The three USP pillars are not three features — they are the three points at which the ledger
gets written to automatically. This framing is what survives the CMDB/data-catalog critique
instead of ignoring it.

## Angle A — "The ledger earns its name or it doesn't"

Lead question: *what would have to be true for this to be an asset register rather than a
database with an expensive name?*

Organising claim: the asset framing is a commitment with a testable consequence — a named
owner, a lifecycle with a retirement path, a record of what uses it, and a cost attached. Judge
the design by whether those four fields are populated and TRUE at day 90, not day 1. Everything
else in the architecture follows from serving that.

Strongest material: the two-tier field logic (auto-derived operational fields vs. semantic
fields captured inside the promote step); MLflow's retreat from fixed stages; CMDB
field-ownership rot; the IAS 38 limitation stated once and honestly; the a fortiori reading of
the GitHub duplication study.

Characteristic risk to guard: drifting into abstraction about "governance" instead of naming
schema fields. This angle must produce an actual field list.

## Angle B — "Build the smallest thing that cannot be bought"

Lead question: *given free versioning primitives in every cloud and brutal internal-tooling
maintenance economics, what is the irreducible built surface?*

Organising claim: everything commodity should be inherited; the four bespoke surfaces are the
cross-provider asset schema, the approval-decision object, the per-runtime push adapters, and
non-content OTel telemetry ingestion. The approval object is the keystone — it is
simultaneously the confirmed market gap, the sanctioned bespoke surface, and the agent's output
target.

Strongest material: Bedrock/Vertex single-project scoping; AWS RAM sharing covering models, not
prompts; the confirmed absence of any pending-review/evidence-record/rejection-path object
across four vendors; Langfuse's caching and guaranteed-availability bar as the reliability
standard any adapter must inherit; the named uncompensated cost of label-based versioning
(no branch/merge, so duplicate clustering becomes the standing compensating control).

Characteristic risk to guard: thin-layer discipline can shrink the product below the point of
being worth adopting. This angle must confront that its own logic excludes the ingestion agent
and embedded capture surfaces that make the product distinctive, and resolve it by sequencing.

## Angle C — "It only counts if the marketer uses it on Monday"

Lead question: *what has to happen in the first sixty seconds, and what does the eval and
approval machinery look like when the person on the other side is not an engineer?*

Organising claim: adoption is a friction differential against Google Sheets, not a feature
comparison against Langfuse. Zero-labor ingestion plus exactly one deliberate wall at promotion.
Everything the eval literature says about subjective-task judging then becomes a design
constraint on what the approver is shown, not an academic caveat.

Strongest material: the spreadsheet-reversion diagnostics; data-catalog entry-ticket failure;
the criterion-referenceability result and what it implies for showing a judge score to a
marketer; the block/report/monitor rule; the destination-vs-capture-surface split; the demo
proof-points.

Characteristic risk to guard: adoption-first reasoning can quietly discard the hard constraints.
This angle must show HITL and RBAC surviving in a form a non-engineer will tolerate, not argue
them away.

## Binding on all three

- Honour every correction in `comparisons.md` (duplication figures, drift attribution, the
  rubber-stamp absence, the two distinct Vietnamese provisions, the Evidently non-finding).
- Engage all five cross-locus tensions and all seven source tensions; the source tensions get a
  dedicated section.
- State plainly that the positive case is vendor-authored and thin while the negative case is
  disinterested and strong, and that the honest basis for mandatory HITL is corporate
  governance rather than a present statutory command on the register itself.
- Never claim the eval gate guarantees no quality degradation. Block on contract, report on
  quality, monitor for drift.
- Carry the audited absences rather than papering over them.

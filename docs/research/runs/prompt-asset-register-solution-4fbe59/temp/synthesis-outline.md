# Synthesis outline — final report

Target 8,500–9,500 words. Every section must RESOLVE something; none may merely describe.

## Lede (unheaded, ~350 words)
The executive answer up front. The register is only as good as the fields it can populate
without anyone maintaining them; the three differentiators are the three points where the
ledger writes itself; two of the four stated constraints cannot be honoured as literally
written and the honest reformulations are better. State the evidence asymmetry once, here.

## 1. What the Asset Framing Commits You To — And the Prior Art It Inherits (~700w)
Resolve: is "asset" earned or decorative? Commit — it is a falsifiable claim requiring four
fields to be true at day 90. IAS 38 limitation stated once and set aside. Prior art: CMDB
decay, data-catalog failure, MLflow's retreat from fixed stages, feature-store scepticism.

## 2. The Asset Record — Prompt Identity, Data Model, and Lifecycle (~1,000w)
Draft A's four-tier schema, kept as tables. Tier 1 auto-derived; Tier 2 captured inside the
promote step; Tier 3 refused. Each row: how populated, what makes it stale. Resolve: MLflow's
alias pattern over a manual status enum.

## 3. Ingestion: Starting From the Existing Chaos (~800w)
Resolve: neither egress capture nor source scanning can see the document-and-chat estate, so
document connectors are a first-class third method and the register must record which method
found each prompt. GitHub duplication figures with the a fortiori inference clearly labelled
as inference. Introduce the two-population register here; it is an ingestion design decision.

## 4. Versioning, Release, and Rollback Mechanics (~700w)
Resolve the prompt-as-code vs prompt-as-content fork in favour of labels, and pay the cost
explicitly: no branch or merge semantics, so duplicate clustering is the standing compensating
control. Immutable versions, movable protected labels, rollback as label reassignment.

## 5. Regression Eval You Can Actually Gate On (~1,100w)
The report's most important section. Criterion-referenceability as the organising variable.
Block on deterministic contract properties; report subjective quality as advisory; monitor for
drift on a schedule. Then Draft C's resolution: the judge SELECTS divergent examples for the
human rather than scoring — retrieval, not ranking. Bootstrapping eval sets from production.

## 6. The Promote Gate — HITL, RBAC, and the Two-Minute Decision (~1,100w)
Resolve DORA vs the constraint: the penalty attaches to external context-poor approval, not to
an accountable owner with pre-computed evidence. State plainly that neither the EU AI Act nor
Vietnam's Law 134/2025/QH15 with Decree 142/2026/ND-CP compels sign-off for an internal
platform; the basis is segregation of duties plus prophylactic readiness. Both Vietnamese
clocks, kept distinct. The approval-object spec. The four-jobs-on-one-card overload risk,
ordered and defaulted, including what the record looks like when the approver just clicks
approve. RBAC drawn around the eval contract, not only prompt text.

## 7. Cost and Token Economics as a Release Control (~600w)
Resolve: prompt length is not cost. Measure cost per successfully completed task including
retries. Showback before chargeback. The compression counter-case.

## 8. Distribution to Products — API/SDK, Parity, and Failure Modes (~600w)
The reliability bar any adapter must inherit: TTL cache, stale-while-revalidate, background
refetch, revert-to-cache on failure, startup prefetch, hardcoded fallback. Non-content OTel
attributes as the telemetry return path. Test/production parity.

## 9. The Agent Layer and the Build / Buy / Layer Decision (~900w)
Draft B's keystone argument, including the Langfuse self-admission. The minimum durable
surface, stated honestly as four plus dedup clustering. The agent reframed: ingestion and
clustering as lead capability; improvement proposals rate-capped, eval-pre-validated, emitted
as evidence cards. Say the ingestion differentiator is novel but unproven.

## 10. Adoption Inside the Organization (~800w)
Friction differential against Sheets, not feature parity with Langfuse. Which Sheets
affordances will not be matched and what compensates. Ledger as destination, capture surface
embedded. Label the analogical distance of this evidence honestly.

## 11. Build Sequence and Demo Proof Points (~700w)
What to build first, what to stub, what to defer. Demo proof-points tied to each claimed value,
including the governed-fraction headline and the single visible moment of friction.

## 12. Where the Framing Breaks — Risks and Counter-Evidence (~700w)
The premise is asserted rather than measured for the internal case. Registry decay is the
strongest disinterested evidence and it points at this product. Rubber-stamping risk and the
instrumentation that detects it. Vendor commoditization. The audited absences.

## Source Tensions (~900w)
All seven, each with both sides and the committed resolution. Compress hard — these are already
adjudicated; state the resolution and the load-bearing reason, not the full argument.

## Opinionated Synthesis (~700w)
The recommendation, ranked and committed. What would falsify it. What the team should do first
on Monday. No new evidence.

---

**Citations:** keep `[note-id]` format throughout. Do NOT write a `## Sources` section — the
orchestrator generates it deterministically after synthesis.

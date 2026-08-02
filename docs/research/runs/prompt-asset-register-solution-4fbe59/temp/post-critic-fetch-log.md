# Step 13 — post-critic gap fetch

**Result: no new fetch wave required.** Every gap the four critics raised is already covered by
a source in the vault. Checked item by item:

| Critic gap | Status |
|---|---|
| EU AI Act Article 14 (human oversight) never read — depth #4, and an undisclosed absence | **Already fetched** during step 8's pre-emptive wave (`article-14-human-oversight-eu-artificial-intelligence-act`). The absence claim in §12 is now itself wrong and the patcher must either use the source or drop the absence. |
| Progressive delivery / canary absent — width #1 | Four feature-flag sources already in vault, all unused: LaunchDarkly, Flagsmith, Unleash (×2), plus the MLflow alias RFC's own A/B sentence. |
| Shared prompt set / "dùng chung" — width #2 | `centralized-prompt-management-for-enterprise-2026-framework` in vault, unused. |
| Showback-before-chargeback — width #3 | `how-to-allocate-ai-cost-a-step-by-step-finops-method-amnic` in vault, unused. |
| MLflow `validation_status` tag guidance — width #6 | `model-registry-workflows-mlflow-ai-platform` in vault, unused. |
| Developer-facing CI contract — width #7 | Both promptfoo CI notes in vault, unused. |
| Prompt security as a contract category — width #8 | `static-analysis-for-llm-prompt-security-...` in vault, cited only for its SBOM by-product. |
| LangSmith / Azure AI Foundry absent from the comparison — instruction #2 | **Genuine corpus gap.** Neither was fetched; the width sweep covered them only through vendor comparison blogs, which the domain notes exclude as evidence. Not fetched now: adding two more vendor rows would grow a report already over its ceiling, and the keystone claim survives being narrowed to the four surfaces actually read. The patcher must instead **narrow the claim's scope wording** from an implied market-wide survey to the four vendors genuinely examined. Recorded as a scope limitation, not silently ignored. |
| Effort/staffing anchor for the build sequence — width #5 | Partially covered by the Retool and Pragmatic Engineer notes; the specific FTE figure sits in an unread source. Treated as an audited absence rather than fetched, since a single staffing ratio would not change the recommendation. |

**Decision:** the binding constraint on this run is now length, not coverage. The report stands at
~12,500 words against a 5,000–10,000 band after two compression passes. Fetching more sources
would add citable material the report has no room to carry. The patcher's mandate is therefore
to spend the critics' findings against existing vault sources and to finish net-negative on
length.

Two orchestrator-level items are handled outside the patcher and should not be patched twice:
- **The missing `## Sources` section** (instruction critic, flagged `requires_orchestrator_restructure`)
  is generated deterministically by `temp/renumber_citations.py`, which converts every
  `[note-id]` marker to a numbered `[N]` and emits a resolvable source list. Run before polish.
- **Retraction re-check** runs at the ship gate.

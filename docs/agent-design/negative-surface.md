# Negative surface — the eval-analysis improvement pipeline

The list of what this pipeline may **never** do. Each line is enforced by a test named beside it
(the test names are commitments in slice 8; the file is the reviewer's checklist and the CI
registry).

| # | It may never… | Because | Enforced by |
|---|---|---|---|
| 1 | create, approve, or release a revision — or hold any path to one | the write is a person's (ADR-0066); accept returns a body and nothing more | `test_accept_writes_no_revision`, `test_release_control_depends_on_four_modules` (existing, still green) |
| 2 | make any outbound request — no webhook, email, Slack, DNS channel of any kind | the module holds private data + untrusted content; the third trifecta leg must be structurally absent (ADR-0068 §5, unchanged) | no HTTP client import in `prompt_improvement` (architecture test pattern) |
| 3 | call a workspace provider outside the gate probe, or retry the probe | gate spend is bounded and single-shot by design | `test_gate_runs_once_and_is_persisted_before_proposal` |
| 4 | open a second proposal while one is open on the same prompt | the queue's rate cap is a DB partial unique index, not a service check | existing `uq_improvement_proposal_one_open_per_prompt` + `test_rate_cap_is_the_database` |
| 5 | persist a model-authored body anywhere except `improvement.proposal` | no second content store to defend (ADR-0068 §1's spirit) | architecture test: no other table gains a body column |
| 6 | propose an edit for a prompt with no attached suite | no suite means no gate; the remedy degrades to a case/note proposal (ADR-0068 §2, unchanged) | existing `test_no_suite_no_edit` |
| 7 | render a candidate that failed or never reached the gate | gate-before-person is the module's core control (ADR-0068 §2, unchanged) | existing `test_the_gate_discards_before_a_person_sees_it` |
| 8 | emit a proposal whose candidate changed the `{{variable}}` set, broke canonical XML, or exceeded the diff bounds | code owns the rails; the model owns only the wording | `test_rails_reject_*` (one per rail) + `test_injection_fixtures` |
| 9 | show the model's rationale as the proposal card | the card is the diff + the gate delta; the rationale is a collapsed, clearly-labelled secondary note | `test_proposal_card_renders_diff_or_refuses` |
| 10 | read prompts or runs the requesting actor cannot see | the run inherits the actor's grants, not the sweep's | `test_manual_run_scopes_to_actor` |
| 11 | auto-trigger on run settlement, schedule, or sweep without a person's click | spend follows a person's request (this design's D2); revisit is an ADR amendment, not a config flip | no settlement hook exists; asserted by route-table shape |
| 12 | put draft cost on the workspace's meter, or probe cost on Prope's | two meters, never added (ADR-0068 §7, unchanged) | `test_draft_cost_never_becomes_a_call_record` |

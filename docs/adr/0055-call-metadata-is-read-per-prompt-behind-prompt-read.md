# ADR-0055 — Call metadata is read per prompt, behind `prompt.read`

**Status**: Accepted
**Date**: 2026-08-12
**Decision**: user (asked and answered during the FE/BE integration)
**Module**: prompt-registry (reader) / call-ledger (read subject)
**Supersedes**: nothing. **Narrows**: the module map's `prompt-registry` dependency list
**Related**: ADR-0018, ADR-0027, ADR-0020, A-040, A-044, BR-01, OQ-013, OQ-006

## Context

The SPA ships a call-records screen. Everything on it — prompt, revision, consuming key,
timestamp, tokens, cost, outcome — is a column of `ledger.call_record`. None of it is a column of
`ledger.call_body`.

ADR-0018 is routinely quoted as *"call-ledger has no read path"*, and that reading is too coarse.
What it decides is that **bodies** are written and deleted and nothing reads them in the MVP. About
everything else it is explicit: *"Metadata is unaffected. It is kept indefinitely, **it has
readers**, and it is the audit trail NFR-02 requires."*

So the screen was never asking for the forbidden thing. What it ran into is a different constraint,
and a sharper one.

The module map gives call-ledger `deps_out: none` and states the forbidden edge as
**call-ledger → anything**. Follow it to the same consequence ADR-0018 followed it to: with no edge
to access-control, **this module cannot check a permission**, so any endpoint it exposes must be one
that needs none.

A workspace-wide call-record list is not such an endpoint. Tenant isolation is free — the row-level
policy scopes every read to `app.workspace_id`, so cross-workspace leakage is impossible whatever
the module does. The problem is *within* a workspace. Every row names a `prompt_id`, and prompts are
**private by default** (BR-01, and one of the four non-negotiables). A flat list would therefore tell
a Viewer that a private prompt exists — which is precisely the disclosure BR-01 closes by answering
not-found, arriving through a door nobody had classified as a read.

## Decision

**The reader is `GET /api/v1/prompts/{prompt_id}/call-records`, it is mounted by prompt-registry,
and it checks `prompt.read`.**

- **Metadata only.** The response names no `call_body` column and no type in the path can carry one.
  `tests/security/test_no_body_read_path.py` asserts that structurally, over the route table, the
  public callables and the read-side types — not by inspection of this file.
- **`actor_id` is excluded as well**, though it is metadata. It names the person who made a call,
  which is a fact about somebody's working day rather than about the prompt. `consumer_key_id` is
  what a reader is actually asking — *which integration is calling this* — and it names a key.
- **The permission check runs before any record is read**, through `_visible_prompt`, so the refusal
  is A-116's two shapes and not a third, and it cannot vary by how much traffic a prompt has had.
- **call-ledger gains no outbound edge and remains a sink.** The new edge is *inbound* —
  prompt-registry → `prope.call_ledger.seams` — which is the direction that was always allowed.
  `test_call_ledger_is_reached_only_through_its_seam_module` bounds it to the seam module, so the
  write path stays out of reach.
- **ADR-0018 is not superseded and its rule is not weakened.** Bodies still have no read path, no
  export, no admin viewer and no debug route.

## Alternatives rejected

**A flat `GET /api/v1/call-records` in call-ledger.** This is the shape the SPA drew, and it is the
one that costs the most. It needs call-ledger → access-control, which ADR-0018 rejects by name and on
where it leads: *"the edge would be defensible for one read API and then available for the next
thing"*. Without that edge it cannot check `prompt.read` at all, so it would either leak the
existence of private prompts or filter on nothing. The screen moves to a tab on the prompt detail
page instead, which is a smaller change than ending a module's sink status.

**Let call-ledger filter to prompts the caller may see, with its own copy of the rules.** Rejected
for ADR-0018's reason, restated: two implementations of *"who may see this"* is the failure the
module map already avoids three times over, and the copy that drifts is always the one nobody is
looking at.

**Query `ledger.call_record` directly from prompt-registry's repository, importing nothing.**
Rejected as worse than the edge it avoids. It would duplicate knowledge of another module's table
shape with no import for a test to see, so the dependency would exist in fact and not in the module
graph — which is the one thing `docs/architecture` is for. ADR-0027 makes schema-qualified names
legible precisely so a cross-schema read is visible; hiding one behind raw SQL inverts that.

**Wait for OQ-013.** Rejected because OQ-013 is about bodies — retention, standing to read, PII and
redaction, residency — and none of its four questions is a question about token counts. Blocking a
metadata read on it would be blocking on an unrelated answer.

## Consequences

- prompt-registry declares **four** module dependencies rather than three, and
  `tests/architecture/test_prompt_registry_depends_on_three_modules.py` records the new one with the
  surface it is bounded to. The file keeps its name; the count in its docstring changed.
- `ix_call_record_workspace_id_prompt_id_created_at` is added in revision `0011` — partial on
  `prompt_id IS NOT NULL`, because evaluation's calls carry a `run_id` and no prompt, and indexing
  those NULLs would grow the index by every row it can never serve.
- **A-040's `read_bodies` permission is still deferred, and this does not stand in for it.** That
  permission is about bodies. If a body reader is ever built, ADR-0018 remains the decision it has to
  reopen, and this one does not make that easier or harder.
- The riskiest data in Prope still has the fewest ways to reach it. What changed is that the least
  risky data next to it now has exactly one, and it runs through a permission check.
- The paging is a keyset over `(created_at, call_id)` rather than an offset, because this is the
  largest table in the system and the newest page is the one anybody opens.

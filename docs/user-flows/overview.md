# Prope MVP User Flows

## Authority

These diagrams describe the enterprise MVP locked by:

- `docs/brainstorm/00_context.md`
- active assumptions under `docs/brainstorm/assumptions/`
- accepted ADRs under `docs/adr/`
- module contracts under `docs/modules/`

Where the older product source of truth conflicts with a later locked decision, the locked decision wins. In particular, A-017 removes individual mode from this MVP and the resolved scope removes external import and similar-prompt clustering.

## MVP journey

```text
Enterprise Registry entry
→ Register a prompt manually
→ Assign one owner and explicit access
→ Create immutable revisions
→ Run all named deterministic eval suites
→ Submit for one-level human review
→ Approve a trusted revision
→ Make a second recorded release decision
→ Restore a previously Approved revision when necessary
```

## Flow inventory

| # | Flow | MVP status |
|---|---|---|
| 01 | `01-enterprise-entry.mmd` | In scope |
| 02 | `02-register-prompt.mmd` | In scope |
| 03 | `03-find-trusted-prompt.mmd` | In scope |
| 04 | `04-manage-ownership-access.mmd` | In scope |
| 05 | `05-manage-revisions.mmd` | In scope |
| 06 | `06-prepare-evaluation-evidence.mmd` | In scope |
| 07 | `07-review-approval.mmd` | In scope; one reviewer |
| 08 | `08-release-approved-revision.mmd` | In scope; separate recorded release decision |
| 09 | `09-restore-revision.mmd` | In scope; target must be previously Approved |
| 10 | `10-similar-prompt-check.mmd` | Deferred; out of MVP |

The connected high-level diagram is in `overview.mmd`.

## Explicitly out of scope

- Individual save → find → reuse mode.
- Import from Sheets, Notion, Drive, repositories, files, or chat exports.
- Similar-prompt clustering and duplicate grouping.
- Semantic or vector search.
- LLM-judge quality scores.
- Multi-level approval and configurable policy engines.

## Evaluation rules carried into the flows

- A prompt owns one or more named, independently versioned suites.
- Each suite contains 10–20 hand-authored deterministic cases.
- One eval run measures one revision against one suite version.
- Candidate evidence is compared with the current released revision using a reusable matching baseline run.
- A first release has no baseline and therefore no cost delta.
- A failed case requires an acknowledgement reason during approval; it does not hard-block approval or release.
- Cost increase is warning-only in the MVP.
- An errored case is not a failed case, and incomplete evidence is not a pass.

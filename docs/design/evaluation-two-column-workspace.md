# Evaluation two-column workspace

## Understanding summary

- The evaluation page must keep dataset selection and prompt evaluation visible as peer work areas.
- A long dataset library must not push the run action or results below the fold.
- The left column owns dataset discovery, selection, creation, editing, and deletion.
- The right column owns the **Run trial** action, readiness state, progress, and results.
- Existing evaluation APIs, provider validation, mutations, and the bottom navigation dock remain unchanged.
- Desktop and tablet use two columns; narrow mobile layouts stack the same two regions without losing semantics.

## Assumptions and non-functional requirements

- The app shell owns the normal document scroll and sticky navigation.
- Dataset libraries and evaluation results grow through one predictable page scroll rather than nested scroll regions.
- No new server calls, persisted UI state, or authorization changes are required.
- Existing keyboard controls, labels, focus rings, loading states, and disabled reasons are preserved.
- The layout must reuse semantic tokens and shared components; no new hardcoded design values or user-facing strings are introduced.

## Final design

The registration steps and page-level notifications remain above the workspace. The workspace becomes a responsive two-column grid with natural page scrolling:

```text
+---------------- dataset library ----------------+--- prompt evaluation ---+
| folders, suites, cases                           | run action               |
| natural page flow                               | readiness / results      |
|                                                  | natural page flow         |
+--------------------------------------------------+--------------------------+
| Back to edit                                      Back to prompt (dock)      |
+----------------------------------------------------------------------------+
```

The dataset column uses `fit-content` with the shared drawer-width cap, so it hugs the actual labels and dataset text without allowing one unusually long name to consume the evaluation area. The evaluation header stays at the top of its column and the results render immediately below it. At narrow widths the regions stack in the same order, with the evaluation region remaining a distinct card. The bottom dock continues to contain navigation only. There are no nested hidden-scroll regions.

## Decision log

1. **Use a two-column workbench.** Accepted because it keeps selection and feedback in the same visual context.
2. **Use natural page scrolling.** This supersedes the initial independent-scroll decision after visual review showed the nested dataset scrollbar felt hidden and constrained.
3. **Keep Run trial in the evaluation column.** Chosen over adding it to the global dock so the action remains attached to its outcome.
4. **Preserve a stacked mobile fallback.** Chosen over compressing both columns on small screens, which would make dataset names and result evidence unreadable.
5. **Do not change backend behavior.** This is a layout and information-hierarchy correction only.

## Verification

- Confirm two visible columns at the application content width shown in the reported screenshot.
- Confirm long dataset and result lists remain reachable through the normal page scroll with no nested scrollbar.
- Confirm Run trial remains visible at the top of the evaluation column.
- Confirm keyboard focus, loading, disabled reason, error, empty, and success states still work.
- Run TypeScript, ESLint, and the production build.

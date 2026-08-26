# Prompt detail dock and display names

## Understanding summary

- Restore the prompt detail workspace as a two-panel dock.
- The left panel owns revision navigation and the two editing entry points.
- The right panel owns the active prompt tab and its information.
- The Content tab includes prompt content, metadata, change log/diff, binding and fallback information.
- Remove the bottom action docks from Content and Evaluation, and remove the Evaluation quick-action row.
- Never present internal user or folder identifiers as human-facing names.
- Resolve revision authors and prompt owners to workspace member display names, and folder namespaces to declared folder names.

## Assumptions and non-functional requirements

- This is a frontend-only change. Existing read and write APIs remain unchanged.
- Member and folder queries are shared through TanStack Query, so display-name resolution does not duplicate server state.
- The dock is side-by-side at the navigation breakpoint and stacks on smaller screens.
- Each desktop panel owns its necessary scroll surface; no nested bottom action dock remains.
- If a removed member has no display name, the UI uses a translated unavailable-member label and never falls back to the technical ID.
- Existing permission, revision-selection and mutation behavior remains unchanged.

## Approaches considered

1. **Restore the existing revision rail and add shared display-name resolution (selected).** Reuses the established component and current APIs; lowest behavior risk.
2. Rebuild a new dock from the current header. Duplicates revision controls and creates another visual variant.
3. Enrich every prompt API response in the backend. Cleaner payloads, but expands scope and changes the backend contract.

## Final design

Desktop layout:

```text
+-----------------------------+-----------------------------------------+
| Revision management         | Active tab information                  |
| [PropAI suggestion]          | Prompt title and friendly folder name   |
| [Manual edit]                | Metadata / change log / prompt content  |
| r3  author · time            | Provider / model / fallback             |
| r2  author · time            |                                         |
| r1  author · time            |                                         |
+-----------------------------+-----------------------------------------+
```

The left rail remains visually quiet and dense, using the existing semantic canvas, surface, border, focus and status tokens. Selection is communicated by the existing inset surface treatment, not by a new decorative card style. On mobile the rail precedes the active tab content.

## Decision log

- Reuse `PromptVersionRail`; it is the deleted design's surviving implementation and already contains the required actions.
- Resolve identities from workspace membership and folders from the folder catalogue at the presentation boundary.
- Do not display model namespace as a folder label; use the declared folder name.
- Keep technical IDs in route values and API payloads only.
- Remove redundant version dropdown/history controls once the rail is restored.
- Remove action bars and Evaluation quick actions exactly as requested, without changing their destination routes elsewhere.

# Focused workbench UX

## Understanding summary

- Playground must remain usable with hundreds of prompts by replacing its native select with a searchable, faceted picker.
- The Playground cost panel stays visible on desktop while the chat column scrolls, and returns to normal document flow on smaller screens.
- Dataset tags are user-owned metadata, so they act as a dynamic filter rather than fixed navigation tabs.
- The Dataset collection needs search, filter, sort, result count, and distinct empty/no-result states.
- Labeling becomes a reviewer workbench with a navigable queue, visible progress, and a focused decision area.
- Saving a label advances to the next unlabeled call without losing the current form when a save fails.
- Existing API contracts, TanStack Query ownership, semantic tokens, i18n, and shared UI primitives remain unchanged.

## Assumptions

- Each client-side collection contains at most a few hundred records; memoized in-memory filtering remains responsive.
- No additional prompt or customer body content is exposed on the labeling surface.
- All four async states remain available and failures preserve the user's current selection and input.
- Desktop sticky behavior begins at the existing `xl` breakpoint; mobile keeps normal reading order.
- The UI is maintained by the existing frontend team, so feature-specific hooks/components are preferred over a highly generic filtering framework.

## Decision log

1. **Focused workbenches, not one universal toolbar.** A shared visual grammar is reused, while each screen exposes only facets that match its data.
2. **Wide modal for prompt selection.** It scales better than a long select and supports richer prompt context without crowding Playground.
3. **Tags become Dataset facets.** Fixed tag tabs were rejected because users can create arbitrary tags and the tab row does not scale.
4. **Master-detail Labeling layout.** It keeps queue position and review context visible, reducing navigation and selection loss.
5. **Auto-advance after a successful label save.** This optimizes the primary reviewer workflow; errors leave the current call and form untouched.
6. **Keep the Prope visual system.** Fraunces remains the restrained display face, Manrope carries controls/data, and existing semantic light/dark tokens supply all color.
7. **One visual signature: the control rail.** Search, facets, sort, active-result count, and reset behavior form a quiet operational strip rather than decorative dashboard chrome.

## Final design

### Playground

The selected prompt is shown in a compact trigger card. Opening it presents a wide modal with search, folder/status/tag facets, sort order, result count, and prompt rows containing title, folder, status, tags, and revision context. The Token and cost column uses desktop-only sticky positioning.

### Datasets

The tag tab row is removed. A control rail searches name, description, and tags; filters by tag and linked-prompt state; sorts by update time, name, or test-case count; and reports the visible result count. The collection distinguishes an empty workspace from filters with no matches.

### Labeling

The page becomes a bounded master-detail workbench. The left queue provides search, label status, outcome, sort, result count, and selected-row state. The right review surface separates call context from the decision form and remains sticky on desktop. Queue progress communicates remaining unlabeled work. Successful saves select the next unlabeled record; failed saves preserve the current record and form.

## Visual system

- Canvas `#FCFBF8`, Surface `#FFFFFF`, Ink `#233B4C`, Teal `#4B7F85`, Signal Yellow `#FDF400`, Border `#D1D7DC`, all consumed through existing semantic tokens.
- Fraunces: page and contextual headings. Manrope: controls, lists, metadata, and data values.
- Motion is limited to existing surface/popover transitions; `prefers-reduced-motion` remains respected.

## Verification

- TypeScript, ESLint, and production build must pass.
- Browser QA covers desktop sticky behavior, mobile flow, keyboard focus, filtered empty states, prompt switching, label save/advance, and console warnings/errors.

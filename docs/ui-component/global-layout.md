# Global layout

Prope is a workspace for prompt governance: calm, evidence-led, and dense enough for operational work without feeling like an admin console. Its visual tone comes from warm canvas surfaces, restrained teal structure, a deliberate yellow primary action, and generous whitespace around decisions.

## Layout principles

- Treat the app shell as a fluid workspace, not a fixed canvas. It must expand, contract, and allow user-controlled resizing without breaking hierarchy.
- Use the semantic background layers deliberately: canvas for the application plane, surface for work areas, subtle for quiet grouping. Keep high-contrast state colors for action and status only.
- Content regions should have `min-width: 0` and grow into available space. Text wraps or truncates according to content importance; it must never force horizontal overflow of the shell.
- Panels may be resized by the user where that helps compare context and work: sidebar versus content, editor history versus main editor, and paired detail panels. A resize operation must preserve each region’s minimum usable content area.
- Do not lock page content to the Figma desktop specimen. The supplied screens show composition and hierarchy, not a mandatory viewport, grid, or breakpoint contract.

## Persistent hierarchy

1. **Navigation context** — persistent rail and top context identify where the user is.
2. **Page action/context** — page title, status, and the primary action remain visually above working content.
3. **Work surface** — tables, editor panels, version history, and notification/chat content occupy the flexible center.
4. **Secondary/support content** — account/help context stays visually quiet and may collapse behind navigation controls when space is limited.

## Information panels and popups

- Route information, notifications, chat history, activity, help, details, and contextual explanations belong in the sidebar or a sidebar-adjacent contextual panel—not in a modal popup.
- The sidebar is the product’s information surface: it can expand, resize, collapse, scroll independently, or become a drawer at narrow widths while preserving the user’s main task.
- Do not use popovers, informational dialogs, or interruptive overlays for content that a user needs to read, browse, or return to. Keep that content persistent or discoverable in the sidebar.
- A modal popup is reserved for a **confirmation card**: an explicit decision that changes, releases, restores, removes, or transfers protected prompt property. It must state the consequence and provide a clear confirm/cancel choice.

## Grouped component blocks

Use **`Depth/Inset/Block`** for a grouped work component: a clearly bounded, white surface in the light theme that gathers related content without becoming a modal or a separate page.

- Background: `--prope-color-bg-surface`—white in the light theme. In dark theme, keep the semantic surface token rather than forcing white.
- Depth: apply the named `Depth/Inset/Block` effect from [tokens.md](tokens.md). Its inset treatment creates a quiet, contained working area against the canvas; do not replace it with a generic drop shadow.
- Purpose: group a coherent unit such as revision history, prompt metadata, editor content, evidence, or a related pair of controls.
- Hierarchy: place the block on the canvas/subtle background and keep its internal content visually calmer than the page title and primary action.
- Composition: a block may resize with the workspace and may sit beside other blocks. It is a structural surface, not a fixed card specimen.
- Boundaries: do not use this style for global navigation, transient information, or confirmation dialogs. Use `Depth/Floating/Soft` for elevated navigation/modal surfaces and the sidebar for information panels.

## Responsive behavior

- Prefer reflow over scaling: columns stack, controls wrap or condense, and metadata moves below its primary label before text becomes unreadable.
- Preserve the user’s task context while adapting: keep the active page, current selection, and primary action reachable.
- Data-heavy tables may scroll horizontally inside their own region. Do not make the complete application shell horizontally scrollable.
- At constrained widths, transform multi-column information into labeled rows or cards only when the reading order remains unambiguous.
- Sidebars, panel splits, and secondary metadata may collapse; the active task surface must remain the priority.
- Persist user-selected layout state when the product supports it: panel widths, collapsed state, and active split should be restored within sensible bounds.

## Product-specific composition

- **Folder Management:** filters are secondary to the registry; make the filter controls wrap/overflow safely while the prompt name and status remain the clearest table signals.
- **Prompt editor:** version history provides context; the prompt’s title, production status, and editing area are the work priority. When space narrows, move history or secondary panels out of the primary flow before reducing editor readability.
- **Notifications and chat:** temporal lists are supporting context. Preserve timestamp association with each message/notification while allowing the list column to become an overlay or a collapsed region.

Use [tokens.md](tokens.md) for visual values and [navigation-bar.md](navigation-bar.md) for adaptive navigation behavior.

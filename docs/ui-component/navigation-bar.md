# Navigation bar

Navigation is a flexible orientation system, not a fixed-width sidebar. It should make the Prope workspace feel stable while giving the user control over how much space navigation occupies.

## Structure and tone

- The persistent rail carries the Prope identity, primary routes (`Home`, `Chat`, `Notification`, `Search`), workspace grouping, and lower-priority account/help context.
- The rail is also the designated information surface. Notifications, chat history, activity, help, and contextual details should open or update here rather than appearing in informational popups.
- The top bar carries the current page’s context and the immediate action (`Create new` or `Setting` in the supplied screens). It is intentionally quiet: page identity first, action second.
- Prompt-editor tabs are local navigation, not global routes. Keep them visually subordinate to the page title and adjacent to the work surface they change.
- Active state must be clear through semantic color, surface, and/or indicator—not through color alone. Use the existing semantic tokens and retain accessible focus visibility.

## Fluid rail behavior

- The rail may be resized by the user. Define a product-owned minimum and maximum in implementation after UX approval; do not derive them from the Figma desktop specimen.
- In its expanded state, show icons and labels. As it contracts, labels may hide and tooltips must expose the route name.
- In an icon-only state, preserve an unambiguous active-route treatment and keyboard focus order.
- At narrow workspace widths, collapse the rail into an overlay/drawer triggered from the top bar. Opening it must move focus into the drawer; closing it restores focus to the trigger.
- Do not simply shrink text, clip labels, or allow the rail to compress the active work surface below its usable minimum.
- Account/help and long history/notification lists are secondary: make them independently scrollable, collapsible, or on-demand rather than forcing the primary route list out of view.
- Information may use the rail’s available space or a sidebar-adjacent panel when richer detail is needed. This panel remains non-modal and must not block work in the main surface.

## Fluid top-bar behavior

- The top bar fills the remaining workspace width and adapts to the rail’s current width.
- Its leading context may wrap to two lines, truncate nonessential description text, or simplify to a breadcrumb/title at constrained widths. The primary action stays reachable.
- If space is limited, move secondary controls into an overflow menu before hiding the primary action or current page identity.
- For a resizable split layout, the top bar belongs to the work surface, not to a fixed page-wide canvas.
- The top bar should remain in view only when it improves task continuity; sticky behavior is an implementation choice, not a Figma requirement.

## Interaction and accessibility

- Use native links for routes and `aria-current="page"` for the active global route.
- Local tabs use `role="tablist"`, `role="tab"`, `aria-selected`, and arrow-key navigation only when they swap in-place panels. Use links when they navigate to a separate URL.
- Rail, drawer, overflow, and resize handles must be fully keyboard-operable. Resize handles need an accessible name and discrete keyboard adjustments.
- Tooltips supplement icons; they do not replace accessible names.
- Preserve focus and selection state when the layout changes, a panel collapses, or the rail switches between expanded and compact modes.

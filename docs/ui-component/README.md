# Prope UI component specs

Source: [Figma — Design System](https://www.figma.com/design/dVGYJ8lWqkx5gSX5PBLa9e/%F0%9F%8C%8D-Prope---Prompt-as-a-property?node-id=36-6). Extracted 2026-08-09 from page `Design System` (`36:6`).

These are implementation-facing specs, not new design decisions. Use the semantic CSS variables in `tokens.md`; do not substitute raw primitive colors in components.

| Document | Scope |
| --- | --- |
| [tokens.md](tokens.md) | colors, type, spacing, radii, elevation |
| [core-components.md](core-components.md) | logo, tag, button, input, card |
| [product-components.md](product-components.md) | product controls, navigation, confirmation modal, registry table |
| [global-layout.md](global-layout.md) | shared desktop shell and four P0 Core Flow screen compositions |
| [navigation-bar.md](navigation-bar.md) | persistent rail, top bars, and prompt-editor tab strip |
| [review-queue.md](review-queue.md) | source ambiguities requiring UX/UI confirmation |

Implementation baseline: Tailwind arbitrary values may reference source variables directly, e.g. `bg-[var(--prope-color-bg-surface)]`, `text-[var(--prope-color-text-primary)]`, and `border-[var(--prope-color-border-default)]`. Provide the same variables in both `light` and `dark` theme scopes.

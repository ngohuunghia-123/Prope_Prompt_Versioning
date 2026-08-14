# Prope Design Context

> Status: Direction A — Heritage Ledger, confirmed 2026-08-07; watercolor decorative layer added 2026-08-08. This document is a design contract only; it does not apply or prescribe implementation changes.

## Product and surface

- **Product:** Prope, a prompt asset register for ownership, revisions, review and trusted release.
- **Primary surface:** B-end workbench / prompt registry.
- **Secondary surface:** Review-and-approval detail.
- **Density:** Medium to high. Overview areas can breathe; lists, evidence and decisions must remain fast to scan.

## Visual DNA

- **Temperament:** Calm, editorial, protective, quietly premium.
- **Metaphor:** A well-kept ledger for valuable operational work.
- **Color:** Warm ivory paper, deep teal ink, muted sky support, sun-yellow decision accent and moss status green.
- **Type:** Editorial serif only for brand, page titles and ownership moments; Inter-style sans for navigation, forms, metadata and dense tables. Vietnamese must fall back cleanly to a system sans.
- **Spacing:** 4px base. Use 24–32px between page-level groups, 16px within panels and 8px in compact controls.
- **Shape/depth:** 8–16px rounded surfaces, fine warm-gray borders and restrained soft shadows. Glass is an occasional overview treatment, never a data-table default.
- **Imagery:** Atmospheric landscape material belongs to marketing, onboarding and empty states—not to registry rows or approval evidence.

### Watercolor decorative layer

- **Purpose:** Add a soft, elegant and modern sense of material without changing the existing design system, layout, typography or component structure.
- **Principles:** Use translucent soft washes, a fine paper grain, irregular organic edges, restrained brush strokes and occasional light splash accents. Each treatment should feel printed on warm paper, never glossy, photorealistic or saturated.
- **Color relationship:** Derive every wash from the existing teal, muted sky, warm ivory, sun-yellow and moss palette. Watercolor colors are decorative only and must not redefine status semantics or primary actions.
- **Legibility:** Keep text, controls and evidence on opaque paper surfaces. Watercolor sits behind content or in a non-interactive accent layer; it must not lower contrast, obscure focus rings or compete with decision signals.
- **Scale:** One primary wash per hero or section, one small accent per card or banner, and sparse splashes only. Prefer asymmetry and generous clear space over repeated patterns.

### Watercolor placement rules

- **Use:** hero and section backgrounds, card corners or headers, informational banners, empty states, and editorial/product illustrations.
- **Avoid:** forms, inputs, tables, navigation, status chips, code, dense metadata and long text areas. These surfaces remain solid, quiet and high-contrast.
- **Dense-workbench exception:** A watercolor layer may frame an overview or empty state, but never appear behind rows, columns, filters, approval evidence or batch actions.
- **Accessibility:** Do not place body text directly on a wash. Respect reduced motion; watercolor is static decoration and never a state indicator.

## Layout DNA

1. Persistent, quiet left navigation; the active area is marked with a soft yellow wash rather than a loud block.
2. Workspace hierarchy: breadcrumb → action → title/search → small metrics → registry table → decision card.
3. Tables preserve stable column alignment and opaque, high-contrast rows. Status always has label + color.
4. Review cards surface evidence deltas before the decision action; yellow means attention/action, not success.

## Motion

- 120ms for hover/focus feedback; 180ms for panel/state transitions; 260ms for drawers or detail changes.
- Easing: `cubic-bezier(0.2, 0.8, 0.2, 1)`.
- Signature motif: a low-contrast evidence sweep across a review card on entry or update.
- Never animate table layout, continuously move status labels, or use motion as a substitute for state clarity.
- Honor `prefers-reduced-motion`: static layout and fade-only state feedback.

## Guardrails

- Do not turn the workbench into a scenic landing page or put raw emoji in UI chrome.
- Do not use yellow for body text, large backgrounds or destructive action.
- Do not use serif text in small labels, code, data grids or long-form editor content.
- Keep keyboard focus obvious, status colors accessible and all decisions readable without color alone.
- Do not treat watercolor as a background fill, a data visualization, an interaction affordance or a replacement for hierarchy.
- Do not stack more than two watercolor assets in one viewport or repeat the same wash across adjacent surfaces.

## Evaluation workspace decision

- Keep the version rail as the comparison control, followed by three summary KPIs and a stable dataset table.
- Scope evaluation mock data by prompt and revision through TanStack Query so the backend endpoint can replace it without reshaping the view.

## Token source

Machine-readable tokens: [`tokens.json`](tokens.json). Watercolor component and asset guidance: [`component-rules.md`](component-rules.md) and [`asset-spec.md`](asset-spec.md). Reusable Design Context profile: `~/.vibe-to-ui/profiles/prompt-vault/`.

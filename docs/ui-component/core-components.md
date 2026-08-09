# Core library

## Logo

- `Logo`: two `24 × 24px` variants, exposed in Figma as `Property 1=Default|Variant2`; source does not name their intended theme/state.
- `Full Logo`: horizontal `64 × 24px`; icon `24px` + text `40 × 17px`, no gap. Use the exported Figma asset/glyph, not a recreated SVG.

## Tag

`Tag` is a pill (`rounded-full`) with `py-1.5 px-2.5`, `gap-1.5`, and source height `21px`.

- Variant property: `State=Default | Neutral | Warning | Success | Danger`.
- Content is text-only in the supplied component. Keep the implementation content-sized; the `94px` canvas width is specimen width, not a required fixed width.
- Apply `Depth/Raised/Soft`; map state color only through the semantic color system.

## Button

- Horizontal, content-sized; `py-3 px-4`, `gap-1.5`, `rounded-[6px]`.
- Source specimen: `91 × 34px`; do not infer a standard control-height token because this differs from the defined `sm=32`, `md=40`, `lg=48` scale.
- Implementation API: `intent="primary | secondary | neutral | success | danger"`; `icon="none | leading | trailing"`; `disabled`; `loading`.
- Map source `Dafault` to `primary`; correct the implementation label to `Default`. Map the unnamed source `Variant4` to `secondary`: a non-destructive alternative action using `--prope-color-bg-secondary` and its hover token.
- `leading` and `trailing` are icon-placement variants. Use a Phosphor icon in the relevant slot; an icon never replaces the accessible button name unless the control is explicitly icon-only and has an `aria-label`.
- Keep the source layout for all text buttons (`py-3 px-4`, `gap-1.5`). The icon shares the same horizontal flow as the label; do not add a second nested clickable target.
- Hover is available for every enabled intent and uses its semantic `*-hover` background where defined. Focus must use the semantic focus border/indicator without moving layout.
- On pointer/key activation, use the shared `motion.md` press response: scale `1 → 0.98 → 1` at `--prope-motion-duration-instant`. This is temporary tactile feedback, not a persistent state; disable it under reduced motion.
- `loading` retains the button width, prevents repeated activation, and communicates progress through `aria-busy`. Do not use a shrinking label or replace the text with an unexplained spinner.

## Input

- Fixed source geometry: `280 × 40px`; horizontal layout, `px-3`, `rounded-lg` (`8px`).
- Variants: `State=Default | Focus | Disabled`.
- Use `--prope-color-border-focus` for focus treatment and `--prope-color-bg-disabled`, `--prope-color-text-disabled`, `--prope-color-border-disabled` for disabled UI. Preserve the supplied `40px` height.
- Set real input semantics (`label`, `name`, `disabled`, `aria-invalid`) outside the visual component; Figma supplies only a value text layer.

## Card

- `320 × 160px`, vertical auto-layout, `p-4`, `gap-2`, `rounded-xl` (`12px`).
- Internal title specimen: `150 × 19px`; body: `288 × 40px`—the latter equals container inner width (`320 - 32`).
- Use `Depth/Floating/Soft`; surface and text must come from semantic variables.

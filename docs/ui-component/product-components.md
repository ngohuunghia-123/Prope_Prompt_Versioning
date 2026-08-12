# Product UI patterns

## Status badge and notification

| Component | Variants | Geometry / layout |
| --- | --- | --- |
| Status Badge | `Tone=Active | Pending | Error | Disabled` | `35px` high; content widths in source vary 49–70px. Keep content-sized. |
| Notification | `Tone=Success | Error | Info` | `430 × 92px`; horizontal; `p-4`, `gap-3`, `rounded-[10px]`. |

Status states should map to the semantic state colors; no raw color literals in component code.

## Selection controls

- `Select`: `300 × 44px`, `p-3`, `gap-2`, `rounded-lg`; variants `Default`, `Focus`, `Filled`, `Disabled`.
- `Checkbox`: horizontal control + label, `gap-2`, `20px` high; variants `Default`, `Selected`, `Disabled`.
- `Radio`: same `20px` / `gap-2` structure; variants `Default`, `Selected`, `Disabled`.
- Bind state to native inputs; the visible label must be clickable and states must not be CSS-only.

## Tabs and segmented control

- `Tab`: variants `Active | Default`; `84 × 26px`, vertical layout, `gap-2`. The active affordance must remain part of the `26px` component height.
- `Segmented control`: `360 × 42px`, horizontal, `p-1`, `gap-1`, outer `rounded-full`. Four equal specimen options are each `82 × 34px` with `p-[10px]`; first option is selected in source.
- Use roving focus / arrow-key behavior for a true tablist; use radio semantics when it changes a mutually exclusive setting rather than page content.

## Navigation

- `Device=Desktop`: `1120 × 64px`; `p-4`, `gap-4`, `rounded-[10px]`.
- `Device=Mobile`: `430 × 64px`; same internal geometry.
- Use `Depth/Floating/Soft`; select the variant from a responsive composition, not CSS scaling of the desktop contents.

## Confirmation modal

- This is the **only** popup/modal pattern in the product. Use it only to confirm an explicit, consequential action (for example: approve, release, restore, remove, or transfer ownership). Informational content belongs in the sidebar, not a popup.
- `430 × 280px`; vertical `p-6`, `gap-[18px]`, `rounded-2xl` (`16px`).
- Header frame: `382 × 32px`, horizontal `gap-2`; title `300 × 27px`; body `382 × 48px`; action row `139 × 35px`, horizontal `gap-[10px]`.
- Use `role="alertdialog"` for irreversible/high-consequence confirmation. Trap focus, name via title, restore focus to the trigger, and use the design-system button variants for actions.

## Prompt Registry table

- Component canvas: `1328 × 941px`; its visible table rows are `1120 × 56px`.
- Each visible row uses horizontal layout with `py-[14px] px-10` and zero gap. There are five specimen rows.
- Keep column definitions outside the row primitive and make the desktop table horizontally scrollable or recompose it at narrow widths; no mobile table variant exists in the supplied system.

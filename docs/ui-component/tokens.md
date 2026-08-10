# Foundations / tokens

## Icon library

Use **Phosphor Icons** as the product icon library. Import icons from `@phosphor-icons/react` (or the equivalent platform package); preserve Figma icon sizing and apply only the semantic icon tokens: `--prope-color-icon-default`, `--prope-color-icon-subtle`, `--prope-color-icon-inverse`, `--prope-color-icon-primary`, and `--prope-color-icon-secondary`.

## Color semantics

Use semantic aliases—not primitive palette values—in UI code.

| Token | Light | Dark |
| --- | --- | --- |
| `--prope-color-bg-canvas` | `#fcfbf8` | `#10212e` |
| `--prope-color-bg-surface` | `#ffffff` | `#233b4c` |
| `--prope-color-bg-subtle` | `#f6f7f8` | `#10212e` |
| `--prope-color-bg-primary` / `-hover` | `#fdf400` / `#d7cf00` | `#fef866` / `#fdf400` |
| `--prope-color-bg-secondary` / `-hover` | `#4b7f85` / `#365f64` | `#6f9a9f` / `#4b7f85` |
| `--prope-color-bg-success` / `-strong` | `#edf2e9` / `#6e8b50` | `#6e8b50` / `#6e8b50` |
| `--prope-color-bg-danger` | `#fcebeb` | `#c72127` |
| `--prope-color-bg-warning` | `#fff7d6` | `#ffba00` |
| `--prope-color-bg-info` | `#e6f2fa` | `#1976bc` |
| `--prope-color-bg-disabled` | `#f6f7f8` | `#233b4c` |
| `--prope-color-text-primary` / `-secondary` | `#233b4c` / `#7a8791` | `#ffffff` / `#d1d7dc` |
| `--prope-color-text-inverse` / `-link` | `#ffffff` / `#365f64` | `#10212e` / `#6f9a9f` |
| `--prope-color-text-danger` / `-success` | `#c72127` / `#526b3b` | `#fcebeb` / `#edf2e9` |
| `--prope-color-text-disabled` | `#d1d7dc` | `#7a8791` |
| `--prope-color-border-default` / `-strong` / `-focus` / `-disabled` | `#d1d7dc` / `#7a8791` / `#4b7f85` / `#f6f7f8` | `#7a8791` / `#d1d7dc` / `#6f9a9f` / `#233b4c` |
| `--prope-color-icon-default` / `-subtle` / `-inverse` / `-primary` / `-secondary` | `#233b4c` / `#7a8791` / `#ffffff` / `#fdf400` / `#4b7f85` | `#ffffff` / `#d1d7dc` / `#10212e` / `#fffde0` / `#6f9a9f` |

## Type

`Display/*` uses **Fraunces Bold**; all other named styles use **Manrope**. The Figma primitive font variables (`Inter`, `Playfair Display`) are separate from these local text styles—do not replace the named styles without design approval.

| Style | Font | Size / line-height | Tracking |
| --- | --- | --- | --- |
| `Display/1` | Fraunces Bold | 56 / 64px | -0.5px |
| `Display/2` | Fraunces Bold | 40 / 48px | -0.3px |
| `Heading/1` | Manrope SemiBold | 32 / 40px | 0 |
| `Heading/2` | Manrope SemiBold | 24 / 32px | 0 |
| `Heading/3` | Manrope Medium | 20 / 28px | 0 |
| `Body/Large` | Manrope Regular | 16 / 24px | 0 |
| `Body/Base` | Manrope Regular | 14 / 20px | 0 |
| `Caption` | Manrope Regular | 12 / 16px | 0 |
| `Overline` | Manrope Medium | 10 / 14px | 0.5px |

## Layout scale

- Spacing: `4, 8, 12, 16, 24, 32, 40, 48, 64px` → `--prope-spacing-*`.
- Radius: `4, 8, 12, 16, 24px`, `full: 9999px` → `--prope-radius-*`.
- Control heights: `sm: 32px`, `md: 40px`, `lg: 48px` → `--prope-control-height-*`.

## Elevation

| Style | CSS equivalent |
| --- | --- |
| `Elevation/0` | none |
| `Elevation/1` | `0 1px 2px rgb(26 24 40 / 5%)` |
| `Elevation/2` | `0 4px 8px rgb(26 24 40 / 8%)` |
| `Elevation/3` | `0 8px 16px rgb(26 24 40 / 10%)` |
| `Elevation/4` | `0 16px 32px rgb(26 24 40 / 12%)` |

Depth styles are purpose-specific: `Depth/Raised/Soft` (buttons, tags, badges), `Depth/Inset/Soft` (inputs, select, wells), and `Depth/Floating/Soft` (cards, navigation, modal). Preserve their multi-shadow definitions from Figma rather than approximating a single elevation level.

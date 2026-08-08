# Prope watercolor asset specification

## Visual family

Create a coherent decorative family inspired by the current moodboard: warm ivory paper, deep teal and muted-sky watercolor, restrained sun-yellow highlights, and occasional moss-green support. The visual language is soft, airy and editorial rather than scenic or photorealistic.

| Asset role | Format and composition | Placement | Limits |
| --- | --- | --- | --- |
| Section wash | Transparent SVG or WebP with an organic edge and broad translucent color field | Hero and section background, anchored to an outer corner or edge | One per section; no text directly over the most saturated area. |
| Card accent | Transparent SVG, small watercolor corner, arc or brush stroke | Card header/corner or outside the body reading area | Decorative only; do not cross fields, status or evidence. |
| Paper surface | Tileable, subtle monochrome raster grain or CSS-compatible texture | Global canvas or sparse overview surfaces | Keep texture intensity low and contrast change imperceptible in dense areas. |
| Splash accent | Small transparent SVG/PNG with sparse pigment flecks | Hero, banner or empty state | One secondary accent maximum; never use as an icon or status cue. |
| Editorial illustration | Transparent WebP/PNG or SVG-style illustration using the same wash family | Empty state, onboarding or product storytelling | Keep separate from tables, forms and review evidence. |

## Asset properties

- **Paper grain:** fine, low-contrast and matte; no noise shimmer, harsh fibers or visible repeated seams.
- **Wash edge:** irregular, feathered and organic; avoid hard geometric masks and symmetric gradients.
- **Brush stroke:** sparse, directional and low contrast; it frames content rather than underlining dense copy.
- **Splash:** light and intentional, never confetti-like or a proxy for success/attention.
- **Color:** use the `watercolor.colors` tokens only; preserve existing semantic token colors for UI states.
- **Opacity:** use `watercolor.washOpacity` tokens. Decorative assets must be composited beneath readable surfaces.
- **Surface:** use `watercolor.paperSurface` tokens to select the paper treatment; use the default surface for tables and forms.

## Delivery and accessibility

- Prefer SVG for abstract washes and strokes; use WebP/PNG only where raster grain or illustration detail is essential.
- Export decorative assets with transparent backgrounds unless the asset itself is the paper surface.
- Provide a 2× raster export for non-vector assets; keep the displayed asset lightweight and avoid full-bleed imagery on workbench screens.
- Mark purely decorative assets as hidden from assistive technology. Give illustrative assets concise, contextual alt text only when they carry meaning.
- Validate at normal and high-contrast viewing conditions: text, focus indicator, status label and table scanability must remain unchanged.

## Naming

Use `watercolor-{role}-{palette}-{intensity}-{variant}`. Example: `watercolor-section-teal-soft-01.svg`.

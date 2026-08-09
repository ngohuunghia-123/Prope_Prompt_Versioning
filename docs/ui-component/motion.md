# Motion

GSAP is the product animation runtime. Motion should explain hierarchy, state change, and feedback—never decorate a static surface.

## Control surface

These CSS custom properties are the only default timing/easing values. Override them in the application theme to tune product-wide motion.

```css
:root {
  --prope-motion-ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --prope-motion-ease-emphasized: cubic-bezier(0.2, 0, 0, 1.2);
  --prope-motion-duration-instant: 100ms;
  --prope-motion-duration-fast: 160ms;
  --prope-motion-duration-base: 240ms;
  --prope-motion-duration-slow: 360ms;
  --prope-motion-distance-enter: 8px;
}
```

`standard` is the default. `emphasized` is reserved for confirmation/decision surfaces; do not use it for navigation or repeated list updates.

## Rules

- Animate only `opacity` and `transform` by default. Do not animate layout dimensions, `top/left`, colors, box shadows, filters, or blur unless the UX review explicitly approves it.
- One user action gets one primary motion response. Avoid simultaneous independent loops or competing transforms on the same element.
- Keep list/table updates stable: existing rows do not move unless their order changed; enter/exit affects only the changed row.
- Use `gsap.context()` in React and call `context.revert()` on cleanup. Kill timelines and `ScrollTrigger`s when their view unmounts.
- Respect `prefers-reduced-motion`. Reduced motion must preserve state visibility and action feedback; use an immediate opacity change or no animation.
- Never use a repeating/ambient animation on editorial text, status badges, primary actions, navigation, or notification lists.

## Interaction contract

| Situation | Motion | Default |
| --- | --- | --- |
| Route/content enter | opacity `0 → 1`, translateY `8px → 0` | `base`, `standard` |
| Modal / confirmation enter | opacity `0 → 1`, translateY `8px → 0`, scale `0.98 → 1` | `base`, `emphasized` |
| Modal exit | reverse the entry transform | `fast`, `standard` |
| Sidebar / tab / filter state | indicator or active-surface transform only | `fast`, `standard` |
| Button press | scale `1 → 0.98 → 1`; only while pressed | `instant`, `standard` |
| Toast / notification enter | opacity `0 → 1`, translateX `8px → 0` | `base`, `standard` |
| New table row | opacity `0 → 1`, translateY `8px → 0` | `fast`, `standard` |

Do not stagger navigation items, table rows, or notification histories during routine updates. A stagger is allowed only for first-load entry of a bounded group, at `fast` delay increments, and must be disabled under reduced motion.

## GSAP implementation

```ts
import { gsap } from 'gsap';

const css = getComputedStyle(document.documentElement);
const ms = (name: string) => Number.parseFloat(css.getPropertyValue(name)) / 1000;
const px = (name: string) => Number.parseFloat(css.getPropertyValue(name));
const token = (name: string) => css.getPropertyValue(name).trim();

export function enterSurface(element: Element) {
  return gsap.fromTo(
    element,
    { autoAlpha: 0, y: px('--prope-motion-distance-enter') },
    {
      autoAlpha: 1,
      y: 0,
      duration: ms('--prope-motion-duration-base'),
      ease: token('--prope-motion-ease-standard'),
    },
  );
}
```

GSAP uses seconds, so the helper converts the CSS `ms` values at runtime. This keeps theme-level overrides authoritative.

## Reduced motion

```ts
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

gsap.to(element, reduceMotion
  ? { autoAlpha: 1, duration: 0 }
  : {
      autoAlpha: 1,
      y: 0,
      duration: ms('--prope-motion-duration-base'),
      ease: token('--prope-motion-ease-standard'),
    },
);
```

Treat reduced motion as a functional variant, not a visual degradation: dialogs still receive focus, selected tabs still update, and success/error feedback remains visible.

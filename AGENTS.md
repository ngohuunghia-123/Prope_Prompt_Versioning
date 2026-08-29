# AGENTS.md

## Stack
Vite + React + TypeScript + Tailwind CSS. Package manager: pnpm.

## Structure
```
src/prope-fe
  components/ui/      # shared primitives: Button, Input, Drawer, Tooltip, Modal
  components/         # composed, feature-agnostic components
  features/<name>/    # feature-scoped components, hooks, api
  lib/                # utils, api client, cn()
  locales/            # i18n resources
```
Import with the `@/` alias, never `../../..`.

## Components
- Max ~150 lines per component. Over that, extract subcomponents or a hook — split by responsibility, not by line count.
- One component per file, named export, `PascalCase.tsx`.
- Frequently used UI (Button, Input, Drawer, Tooltip, Modal…) lives in `components/ui/` and is **always reused**. Never create a one-off variant — extend the shared component with a new prop/variant.
- Build variants with `cva` + `tailwind-merge` via a `cn()` helper. Every primitive forwards `className` and `...props` so callers can extend without forking.
- Logic heavier than ~10 lines goes into a `use*` hook next to the component.

## Styling
- **Never hardcode design values in class names.** No `gray-500`, `#fff`, `text-[13px]`, `mt-[7px]`. Use semantic tokens: `bg-surface`, `text-muted`, `border-subtle`, `text-danger`.
- Define tokens in `@theme` (Tailwind v4) or `tailwind.config.ts` (v3) before using them. Adding a token is part of the task, not a follow-up.
- Tokens must be theme-aware (light/dark) so components never branch on theme.
- Tailwind utilities only — no CSS modules, no styled-components, no inline `style` except truly dynamic values (computed transforms/positions).
- Mobile-first: base styles, then `sm: md: lg:`.
- **Never edit style.css.**

## i18n
- Zero hardcoded user-facing strings. All text goes through `t()` (i18next / react-i18next).
- Keys are namespaced and semantic: `checkout.summary.title`, not `text1`.
- Keep all locale files in sync — adding a key means adding it to every locale.
- Use i18n formatters for dates, numbers, currency, and plurals. Never concatenate translated fragments.

## Data & state
- Server state: TanStack Query. Never fetch in `useEffect`.
- Local UI state: `useState`/`useReducer`. Global client state only when genuinely shared (Zustand or Context).
- Every async view handles all four states: loading, empty, error, success.
- API calls live in `features/<name>/api.ts` — never inline `fetch` in a component.
- BE not current;y available, return mock data at Tanstack level so that I can replace with real endpoint easier later

## TypeScript
- `strict: true`. No `any`, no non-null `!` to silence the compiler.
- Type props explicitly; infer return types.
- Validate external data (API responses, forms) with Zod.

## Forms
`react-hook-form` + Zod resolver. No manual `onChange` state per field.

## Accessibility
- Semantic HTML first; `<div onClick>` is not a button.
- Every input has a label; icon-only buttons have `aria-label`.
- Keyboard reachable, visible `focus-visible` ring, correct focus trap in modals/drawers.

## Performance
- Lazy-load routes with `React.lazy` + `Suspense`.
- Lists need stable `key`s — never the array index for reorderable data.
- Add `memo`/`useMemo`/`useCallback` only for a measured problem.

## Testing
This repository keeps **no committed test suite** — there is no `tests/` directory, no pytest config, and no test tooling in the dependency set. Tests are session-local artifacts:

- Write tests only inside the session that needs them, run them only in that session.
- When all tests pass, **delete every test file before ending the session.** Nothing test-related is committed: no test files, no pytest/conftest config, no test-only dependencies.
- The standing gates are lint (`make lint`) and, for the SPA, `pnpm tsc --noEmit` + `pnpm lint` + `pnpm build`.

## Done means
`pnpm tsc --noEmit`, `pnpm lint`, and `pnpm build` all pass. No new console errors or warnings.

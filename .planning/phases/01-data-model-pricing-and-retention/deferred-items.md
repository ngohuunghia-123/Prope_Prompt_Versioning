# Phase 01 — Deferred Items

Out-of-scope discoveries made during execution. Recorded, not fixed.

## Pre-existing lint violations in `scripts/` (found during plan 01-01, Task 1)

`scripts/` holds the `.ai-log` course-logging tooling carried in from a
different project. It is not Prope code, it is named in `01-CONTEXT.md`
§ "Established Patterns" as a scaffold remnant rather than a pattern to
follow, and the Makefile's `lint` target scopes to `src/ tests/ alembic/`.

All eight violations pre-date this phase — none was introduced by the
`py311` → `py313` bump (`UP017` fires from py311 onward, and `I001` / `N806` /
`F541` are target-version independent). `ruff.toml` now excludes the directory
so `ruff check .` gates on Prope's own code; the violations are listed here so
excluding them is a recorded decision rather than a disappearance.

| Rule | File | Detail |
|------|------|--------|
| I001 | `scripts/log_antigravity.py:43` | Import block un-sorted |
| I001 | `scripts/log_hook.py:6` | Import block un-sorted |
| N806 | `scripts/log_hook.py:160` | `_PAYLOAD_KEYS` — non-lowercase local |
| N806 | `scripts/log_hook.py:162` | `_LIFECYCLE_EVENTS` — non-lowercase local |
| I001 | `scripts/log_manual.py:22` | Import block un-sorted |
| F541 | `scripts/log_manual.py:85` | f-string with no placeholders |
| I001 | `scripts/submit_log.py:12` | Import block un-sorted |
| UP017 | `scripts/submit_log.py:45` | `timezone.utc` → `datetime.UTC` |

**Disposition:** leave to whoever owns the `.ai-log` tooling. Six of the eight
are `ruff check --fix` fixable if that owner wants them gone.

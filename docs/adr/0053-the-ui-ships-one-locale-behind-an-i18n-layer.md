# ADR-0053 — The UI ships one locale, Vietnamese, behind an i18n layer built in from day one

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — the UI is not a module; the API contract half of this decision touches all six modules with a management surface
**Related**: A-018 (confirmed by this decision), A-045, A-046, A-150, ADR-0003, ADR-0025, ADR-0048,
ADR-0052, OQ-010, `00_context.md#glossary`, `prope_source_of_truth.md` §18 rule 9

## Context

OQ-010 asked what language the product interface is in. It had three options — Vietnamese with English
status labels, fully English, or a bilingual toggle — and A-018 recorded the first as a working default
because the team's own documents and the demo audience are Vietnamese while the source of truth is
English and requires statuses to stay literal.

**The user answered on 2026-08-09: multiple languages, translated through i18n, with only Vietnamese
implemented for the MVP.** That is neither option 1 nor option 3 exactly. It is option 1's shipped
surface with option 3's structure underneath — and the distinction is the whole decision, because the
expensive part of a second language is never the second translation file. It is that a codebase written
against one language grows hundreds of literal strings, concatenated sentences, and English-shaped
plural and date assumptions, and the second locale then costs a rewrite rather than a file.

## Decision

**One locale ships. The layer that makes a second one cheap is built now.**

1. **Every user-facing string in the SPA comes from a message catalogue**, keyed by a stable
   identifier. No literal display text in a component, including error text, empty states, button
   labels, and validation messages. This is the rule the decision actually buys; the rest follows.
2. **`vi` is the only catalogue in the MVP**, and it is the default and only selectable locale. There
   is no language switcher, no locale negotiation from `Accept-Language`, and no per-user language
   setting — those are what a second locale adds, not what the layer requires.
3. **The keys are English, and they are identifiers, not fallbacks.** A missing key renders the key,
   visibly, and a CI check fails the build on any key present in the code and absent from `vi`.
4. **The five statuses stay literal in storage and in the API**: `Draft`, `In review`, `Approved`,
   `In use`, `Retired` (rule 9). They are translated at the point of display like any other string —
   the stored value never changes, and no code compares a translated label.
5. **The API stays English and stays machine-readable.** ADR-0003's envelope already carries a stable
   machine `code` beside a human `message`. **The client renders the `code`, not the `message`.** The
   `message` remains an English developer-facing sentence, and is what appears in logs.
6. **Human-authored content is never translated.** Approval comments, release reasons, break-glass and
   acknowledgement reasons, prompt bodies, prompt purposes, eval case inputs and fallback answers are
   rendered exactly as written ([[A-046]]). A translation layer over user content would falsify an
   audit record, which is the one thing this product exists to keep honest.
7. **Every registered history action gets a catalogue key** (31 of them as of ADR-0054), derived from
   `property-history.registered_actions()` (INT-008) rather than hand-listed, so an action added
   without a translation fails the same CI check as any other missing key.

## Consequences

- The MVP is Vietnamese to the panel and to the pilot, which is what the audience needs.
- The second locale is a file, a switcher and a per-user setting — a bounded piece of work rather than
  an audit of every component.
- **ADR-0048's search index now sits under a premise this decision changed.** Registry search is a
  trigram index over a trigger-maintained document column, chosen when nothing had established what
  language prompt bodies and purposes would be written in. A Vietnamese-language product means
  Vietnamese diacritics in the indexed text, and a trigram match on `tieu de` does not find `tiêu đề`.
  [[A-150]] settles it inside the existing trigger rather than by adding an index expression.
- Statuses in English inside a Vietnamese screen is a deliberate, defensible choice, and it is now
  defensible in one sentence: the status is a value, not a word.
- Nothing about this reaches the gateway. `/v1` is OpenAI's contract and carries no Prope copy.

## Alternatives rejected

**Ship Vietnamese literals now, extract them when a second language is needed.** The cheapest thing to
write and the most expensive thing to have written. It is also the option that looks identical to this
one for the whole of the MVP, which is exactly why it needs to be rejected explicitly rather than
arrived at by omission.

**Ship both `vi` and `en` now.** Doubles the translation surface for an audience that is entirely
Vietnamese, and every string written twice is a string that can disagree with itself. The layer is
what was asked for; a second catalogue is not.

**Server-side translation — return translated `message` values.** Puts product copy in six modules'
error paths, makes the log line locale-dependent, and would mean a translation change requires a
backend deploy. The `code` already exists precisely so this is unnecessary.

**A bilingual toggle in the MVP (OQ-010 option 3).** Rejected by the answer itself: multi-language
capability, single-language delivery.

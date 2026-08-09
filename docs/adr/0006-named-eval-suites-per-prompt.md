# ADR-0006 — A prompt carries several named eval suites; runs, baselines, and deltas are per suite

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: user
**Module**: evaluation (written while locking it)
**Related**: A-004 (amended), A-016, A-026, A-057, A-058, A-061, A-062, A-063, ADR-0004

## Context

`00_context.md#scope` and the original A-004 both described a single fixed suite of 10–20 cases per
prompt property. Two facts arrived on 2026-08-08 that the single-suite model does not survive.

First, a prompt has more than one thing that can be true about it at once. A reviewer reading "3 of 20
failed" cannot tell whether the revision became less safe or merely changed its output format, and those
two facts deserve opposite reactions on the same screen.

Second, Prope manages every kind of prompt, not only chatbot prompts. It attaches a system prompt and
routes to the destination agent over an OpenAI-compatible chat-completions call, and returns what comes
back. The transport does not widen (A-026 stands, the gateway still implements chat completions and
`/v1/models` only), but the `content` returned is no longer assumed to be prose — a target agent may
return an asset reference or structured data. A single suite implies a single assertion vocabulary, and
that assumption no longer holds either.

## Decision

A prompt property owns several eval suites, each with an author-chosen name unique within that prompt,
each versioned separately, and each declaring its own `output_modality` (A-061).

- Suite identity is `(prompt_id, name, suite_version)`. Editing a suite creates the next version of
  *that* suite and leaves the others untouched.
- Submitting a revision runs every suite the prompt currently has, one `eval_run` per suite.
- Baseline pairing (ADR-0004) needs no change: it already keys on `suite_id`, and `suite_id` now encodes
  the name as well as the version.
- The review summary is a per-suite list plus a rollup. `requires_acknowledgement` (A-058) is true if
  **any** suite has a failing case. The total cost delta is withheld whenever any suite withheld its own
  (A-057); the valid per-suite deltas are still shown.
- The concurrency bound becomes global per workspace, not per run (A-063).

## Alternatives rejected

**One suite, cases grouped by tag.** The cheapest option, and it fails at the only moment that matters.
A tag groups rows in a table; it does not give the reviewer a sentence. "The safety suite regressed" is a
decision; "3 cases tagged safety are red" is a table the reviewer has to interpret under time pressure.
Tags also cannot carry a per-suite `output_modality` or a per-suite version, so a change to one group's
cases would invalidate the baseline for every other group.

**A suite per revision instead of per prompt.** Rejected for the reason A-004 gave originally and still
gives: two revisions measured with two different yardsticks produce a comparison that looks
authoritative and means nothing.

**Keep one suite and widen the assertion vocabulary to cover every modality at once.** Rejected: an
authoring UI that offers substring-match and asset-count in the same list invites cases that can never
pass, and the mismatch is only discovered at run time as a wall of red.

**Let the reviewer choose which suites to run at submit time.** Rejected for the MVP: it makes the
cheapest path the least informative one, and the failure mode is silent — nobody notices the safety suite
was skipped until after the release. Running all of them is the default; the cost is bounded by A-063
and by baseline reuse.

## Consequences

- Dispatch volume multiplies by the number of suites. A-063 makes the concurrency bound global, and
  ADR-0004's baseline reuse changes from a nice saving to a load-bearing one.
- The 120 s p95 target in `00_context.md#success` is stated per suite, not per submit. A submit with N
  suites takes proportionally longer, and the run rows make the queue visible rather than hiding it.
- `00_context.md#scope` and its glossary entry for *eval suite* were amended, and A-004's statement was
  amended in place. Its rationale survives unchanged, applied per suite.
- Suite names are user-authored text and therefore inherit OQ-010's interface-language answer; they are
  never used as identifiers in an API path.

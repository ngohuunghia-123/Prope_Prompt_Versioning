"""The closed vocabularies, and the two maps that keep the model inside them.

:class:`DetectorId` is what a client renders. ADR-0053: the API returns the
machine ``code`` and the client owns the sentence, so a detector with no ``vi``
key fails CI (AC-11) rather than reaching somebody as an English string in a
Vietnamese interface.

:class:`Severity` is imported from ``prompt_readiness`` rather than redeclared.
There are two members and there is no ``blocker``, for ADR-0067 §4's reason
applied with more force: a post-publish finding has even LESS standing to gate a
future decision than a pre-publish one. A third value that did nothing would be
an argument for making it do something, filled in later by whoever is in a hurry.

:data:`REACHABLE_FAMILIES` is the load-bearing map in this file. It is what makes
*"the model picks a remedy"* safe: the model chooses from the tuple this map
already returned for the anomaly, and a family outside it is dropped before
storage. Free-form rewriting does not exist (ADR-0068 §3), and this is where that
sentence is a data structure rather than a paragraph.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any, Final

from prope.prompt_readiness.domain import (
    MAX_EVIDENCE_CHARACTERS,
    Severity,
    redact_evidence,
)

__all__ = [
    "DEFAULT_CADENCE_DAYS",
    "DEFAULT_SEVERITY",
    "DIFF_MAX_RATIO",
    "DIFF_MIN_RATIO",
    "MAX_CHANGED_BLOCKS",
    "MAX_DRAFT_ATTEMPTS",
    "MAX_EVIDENCE_CHARACTERS",
    "PROBE_CASE_CAP",
    "PROPOSAL_TTL",
    "RATIONALE_CHARACTERS",
    "REACHABLE_FAMILIES",
    "REMEDY_KIND",
    "WINDOW",
    "Anomaly",
    "DetectorId",
    "FindingStatus",
    "ProposalStatus",
    "RemedyFamily",
    "RemedyKind",
    "Severity",
    "TerminationReason",
    "WindowPair",
    "bounded_evidence",
    "detector_for_assertion",
]

#: How much traffic one detector pass compares. A day against the day before it.
#:
#: **A window comparison and not a baseline model, which is A-165 and a stated
#: weakness rather than an oversight.** A prompt whose traffic is seasonal — a
#: Monday spike, a month-end batch — can produce a finding that is a calendar
#: artefact. The alternative is a learned baseline, which is a second thing to be
#: wrong about and one nobody can read; the mitigation is that these are
#: dismissible with a reason, and the reasons are what would justify building
#: the baseline.
WINDOW: Final = timedelta(days=1)

#: How long an undecided proposal stays open. OQ-158 owns whether fourteen is
#: right; what is settled is that the number exists and lives in one place.
#:
#: **Expiry closes the PROPOSAL only and leaves the finding open.** A finding is a
#: fact and a proposal is an offer: if the fact is still true the next sweep bumps
#: its occurrence count, and the rate-cap slot the expiry freed admits a fresh
#: offer. Closing the finding too would mean a signal that nobody decided about
#: disappears, which is the opposite of what an undecided proposal should cause.
PROPOSAL_TTL: Final = timedelta(days=14)

#: The default re-probe cadence, weekly. `improvement.schedule.cadence_days`
#: carries it per workspace and the migration's CHECK bounds it to 1..90.
DEFAULT_CADENCE_DAYS: Final = 7


class DetectorId(StrEnum):
    """The closed detector catalogue. Every member needs a ``vi`` key (AC-11).

    Grouped by where the evidence comes from, because that is what a reader most
    needs to know before deciding whether to act: eleven are arithmetic over
    metadata Prope already holds, and the last two are not from the ledger at all.
    """

    # --- from `ledger.call_record` metadata, free, every day -----------------
    #: Context overflow, or `max_tokens` set too low. The caller is paying for
    #: tokens it throws away.
    TRUNCATION_RISING = "truncation_rising"
    #: **The released revision is failing upstream and users are getting the
    #: fallback answer.** Nothing else in Prope pages on this.
    FALLBACK_RISING = "fallback_rising"
    #: The integration is broken — a missing variable, a dropped messages shape.
    #: Usually a migration that shipped half-done.
    CALLER_ERROR_CLUSTERING = "caller_error_clustering"
    #: The model got chattier. Output costs five to six times input, so this is
    #: the largest silent cost regression available.
    OUTPUT_RATIO_DRIFT = "output_ratio_drift"
    #: The provider stopped reporting usage. Every cost figure after this is
    #: MISSING rather than zero, and a dashboard that renders it as zero is
    #: reporting an outage as thrift (A-101).
    USAGE_UNKNOWN_APPEARING = "usage_unknown_appearing"
    #: A new upstream model is serving traffic with no price row behind it.
    COST_UNPRICED_APPEARING = "cost_unpriced_appearing"
    #: The tail is the experience and the mean hides it.
    LATENCY_TAIL_SHIFT = "latency_tail_shift"
    #: **Consumers are pinning away from the released revision.** A governance
    #: signal no competitor has, because no competitor is on the request path.
    PINNED_SHARE_RISING = "pinned_share_rising"
    #: Retry or loop behaviour in the caller's agent, read as a rising share of
    #: calls that carry a `parent_call_id`. A proxy, and named as one.
    CHAIN_DEPTH_RISING = "chain_depth_rising"
    #: Released for a long time and called by nobody — a governed prompt that is
    #: only costing somebody a review. A cleanup finding.
    RELEASED_BUT_UNUSED = "released_but_unused"

    # --- not from the ledger -------------------------------------------------
    #: The property's current Usage Profile no longer matches the copy stamped on
    #: the released revision: *serving the public; approved as internal*. **The
    #: payoff of ADR-0067's D-02** — without the stamp this is undetectable
    #: rather than merely unimplemented.
    PROFILE_DRIFT = "profile_drift"
    #: The scheduled re-probe leaked where the pre-release probe refused. The
    #: guardrail became bypassable and nothing errored, which is deck 6 slide
    #: 25's drift and the reason the opt-in re-probe is worth its money.
    PROBE_LEAK_APPEARED = "probe_leak_appeared"

    # --- from `evaluation`, on a person's click (ADR-0070) --------------------
    #: One member per assertion type the deterministic advisor groups by, so a
    #: recurrence of the SAME kind of failure bumps one row rather than opening
    #: seven. The closed catalogue above stays free of model judgement; these
    #: are the advisor's arithmetic, re-expressed as detector ids.
    EVAL_ASSERTION_REGEX = "eval_assertion_regex"
    EVAL_ASSERTION_FORBIDDEN_PHRASE = "eval_assertion_forbidden_phrase"
    EVAL_ASSERTION_REQUIRED_PHRASE = "eval_assertion_required_phrase"
    EVAL_ASSERTION_JSON_SCHEMA = "eval_assertion_json_schema"
    EVAL_ASSERTION_MAX_LENGTH = "eval_assertion_max_length"
    EVAL_ASSERTION_MAX_LATENCY = "eval_assertion_max_latency"
    EVAL_ASSERTION_MAX_COST = "eval_assertion_max_cost"
    #: An assertion type the advisor did not know. The remedy path treats it
    #: exactly like the others; the card renders the generic advice.
    EVAL_ASSERTION_GENERIC = "eval_assertion_generic"


class RemedyKind(StrEnum):
    """What a proposal offers. Chosen by Prope, never by the model."""

    #: A fact somebody should know. No change proposed.
    NOTE = "note"
    #: A LIBRARY dataset a person ticks — never an attachment, never a suite.
    #: evaluation's rule, and evaluation's reason.
    CASE = "case"
    #: A candidate body from the closed family set, already through the gate.
    EDIT = "edit"


class RemedyFamily(StrEnum):
    """The closed edit catalogue. Three, and growing costs a migration.

    Each is a bounded, parser-derived transform over canonical XML: it may add or
    replace ONE block and must round-trip with an identical declared-variable set
    (SR-4). `ck_improvement_proposal_remedy_family_values` holds the same three
    strings, so a family that reached a row from anywhere else is refused by the
    engine — the posture ``Action`` already takes.
    """

    #: The body tells the model what to do and not what to refuse. Adds or
    #: replaces a `<constraints>` block with an explicit refusal path.
    TIGHTEN_REFUSAL_BLOCK = "tighten_refusal_block"
    #: Adds or replaces an `<output_format>` block naming a length bound.
    ADD_LENGTH_RULE = "add_length_rule"
    #: Adds a brevity clause to `<constraints>`, for the cost regression that
    #: `output_ratio_drift` measures.
    ADD_BREVITY_CLAUSE = "add_brevity_clause"
    #: **ADR-0070.** The candidate body is authored by the App Agent and bounded
    #: by the rails in `rails.py`, not produced by a transform here. A member of
    #: the closed catalogue for the drift families only — an `llm_edit` proposal
    #: still carries body, family, gate run and delta, exactly as
    #: `ck_improvement_proposal_an_edit_is_gated` demands.
    LLM_EDIT = "llm_edit"


class FindingStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    #: The signal went away. Written by the sweep, never by a person, so the
    #: dismissal rate per detector is not polluted by findings that fixed
    #: themselves.
    RESOLVED = "resolved"


class ProposalStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


#: What each detector's remedy KIND is. Prope's decision, made from the anomaly
#: alone and before the model is called at all.
#:
#: **`profile_drift` is note-only on purpose.** A declaration is a person's to
#: change, and a module that proposed an edit to it would be inferring the
#: profile through the back door — exactly what A-163 forbids.
#:
#: **Every eval-backed detector is `edit` (ADR-0070).** The advisor's finding
#: exists because assertions failed, and a person who clicked "propose a fix"
#: asked for an edit; the no-suite precondition still degrades the remedy to a
#: case proposal, exactly as it does for drift.
REMEDY_KIND: Final[dict[DetectorId, RemedyKind]] = {
    DetectorId.TRUNCATION_RISING: RemedyKind.EDIT,
    DetectorId.FALLBACK_RISING: RemedyKind.EDIT,
    DetectorId.CALLER_ERROR_CLUSTERING: RemedyKind.NOTE,
    DetectorId.OUTPUT_RATIO_DRIFT: RemedyKind.EDIT,
    DetectorId.USAGE_UNKNOWN_APPEARING: RemedyKind.NOTE,
    DetectorId.COST_UNPRICED_APPEARING: RemedyKind.NOTE,
    DetectorId.LATENCY_TAIL_SHIFT: RemedyKind.NOTE,
    DetectorId.PINNED_SHARE_RISING: RemedyKind.NOTE,
    DetectorId.CHAIN_DEPTH_RISING: RemedyKind.NOTE,
    DetectorId.RELEASED_BUT_UNUSED: RemedyKind.NOTE,
    DetectorId.PROFILE_DRIFT: RemedyKind.NOTE,
    DetectorId.PROBE_LEAK_APPEARED: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_REGEX: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_FORBIDDEN_PHRASE: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_REQUIRED_PHRASE: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_JSON_SCHEMA: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_MAX_LENGTH: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_MAX_LATENCY: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_MAX_COST: RemedyKind.EDIT,
    DetectorId.EVAL_ASSERTION_GENERIC: RemedyKind.EDIT,
}

#: **The map that bounds the model.** Which edit families an anomaly makes
#: reachable — and for every other detector, none at all.
#:
#: The model is asked to pick from the tuple this returns for the anomaly it is
#: ranking. A family outside it is dropped before storage rather than argued with,
#: which is why `triage` can accept a string from a model without that string
#: being able to become a body transform nobody sanctioned.
#:
#: **Every eval-backed detector reaches exactly `llm_edit` (ADR-0070)** — the
#: bounded-diff, rails-checked authored edit. Drift detectors keep the three
#: clause families; a drift anomaly never reaches `llm_edit`, because drift's
#: remedy space is the one the closed catalogue already states.
REACHABLE_FAMILIES: Final[dict[DetectorId, tuple[RemedyFamily, ...]]] = {
    DetectorId.PROBE_LEAK_APPEARED: (RemedyFamily.TIGHTEN_REFUSAL_BLOCK,),
    DetectorId.FALLBACK_RISING: (RemedyFamily.TIGHTEN_REFUSAL_BLOCK,),
    DetectorId.TRUNCATION_RISING: (RemedyFamily.ADD_LENGTH_RULE,),
    DetectorId.OUTPUT_RATIO_DRIFT: (RemedyFamily.ADD_BREVITY_CLAUSE,),
    DetectorId.EVAL_ASSERTION_REGEX: (RemedyFamily.LLM_EDIT,),
    DetectorId.EVAL_ASSERTION_FORBIDDEN_PHRASE: (RemedyFamily.LLM_EDIT,),
    DetectorId.EVAL_ASSERTION_REQUIRED_PHRASE: (RemedyFamily.LLM_EDIT,),
    DetectorId.EVAL_ASSERTION_JSON_SCHEMA: (RemedyFamily.LLM_EDIT,),
    DetectorId.EVAL_ASSERTION_MAX_LENGTH: (RemedyFamily.LLM_EDIT,),
    DetectorId.EVAL_ASSERTION_MAX_LATENCY: (RemedyFamily.LLM_EDIT,),
    DetectorId.EVAL_ASSERTION_MAX_COST: (RemedyFamily.LLM_EDIT,),
    DetectorId.EVAL_ASSERTION_GENERIC: (RemedyFamily.LLM_EDIT,),
}

#: The severity each detector opens at.
#:
#: **Severity says how bad the fact is, not how convenient the remedy is**, and
#: the two deliberately come apart. Most `note` detectors are `advice` — a cost
#: ratio nobody can fix from here should not outrank a break somebody can — but
#: three are `warning` with no edit behind them, and each earns it: a broken
#: integration (`caller_error_clustering`) is users getting errors, consumers
#: pinning away (`pinned_share_rising`) is production disagreeing with the
#: approval record, and `profile_drift` is a prompt serving under an exposure
#: nobody approved. Downgrading those to `advice` for the sake of a tidy rule
#: would be letting the remedy catalogue decide what counts as serious.
DEFAULT_SEVERITY: Final[dict[DetectorId, Severity]] = {
    DetectorId.TRUNCATION_RISING: Severity.WARNING,
    DetectorId.FALLBACK_RISING: Severity.WARNING,
    DetectorId.CALLER_ERROR_CLUSTERING: Severity.WARNING,
    DetectorId.OUTPUT_RATIO_DRIFT: Severity.ADVICE,
    DetectorId.USAGE_UNKNOWN_APPEARING: Severity.ADVICE,
    DetectorId.COST_UNPRICED_APPEARING: Severity.ADVICE,
    DetectorId.LATENCY_TAIL_SHIFT: Severity.ADVICE,
    DetectorId.PINNED_SHARE_RISING: Severity.WARNING,
    DetectorId.CHAIN_DEPTH_RISING: Severity.ADVICE,
    DetectorId.RELEASED_BUT_UNUSED: Severity.ADVICE,
    DetectorId.PROFILE_DRIFT: Severity.WARNING,
    DetectorId.PROBE_LEAK_APPEARED: Severity.WARNING,
    # Eval-backed detectors default to `advice` and are OVERRIDDEN at intake
    # with the advisor's own arithmetic (share >= 0.1 is warning). The map
    # carries the floor, because `Anomaly.severity` must answer for a member
    # nobody overrode, and a wrong floor fails loud rather than quietly.
    DetectorId.EVAL_ASSERTION_REGEX: Severity.ADVICE,
    DetectorId.EVAL_ASSERTION_FORBIDDEN_PHRASE: Severity.ADVICE,
    DetectorId.EVAL_ASSERTION_REQUIRED_PHRASE: Severity.ADVICE,
    DetectorId.EVAL_ASSERTION_JSON_SCHEMA: Severity.ADVICE,
    DetectorId.EVAL_ASSERTION_MAX_LENGTH: Severity.ADVICE,
    DetectorId.EVAL_ASSERTION_MAX_LATENCY: Severity.ADVICE,
    DetectorId.EVAL_ASSERTION_MAX_COST: Severity.ADVICE,
    DetectorId.EVAL_ASSERTION_GENERIC: Severity.ADVICE,
}

#: The advisor's assertion-type VALUES, mapped onto the detector that carries
#: them. Strings rather than `evaluation.AssertionType` members so this module's
#: domain stays importable without `evaluation` — the same lightness
#: `WindowPair`'s ``Any`` typing buys. An unknown type maps to the generic
#: member, which is the advisor's own fallback shape.
_ASSERTION_DETECTORS: Final[dict[str, DetectorId]] = {
    "regex": DetectorId.EVAL_ASSERTION_REGEX,
    "forbidden_phrase": DetectorId.EVAL_ASSERTION_FORBIDDEN_PHRASE,
    "required_phrase": DetectorId.EVAL_ASSERTION_REQUIRED_PHRASE,
    "json_schema": DetectorId.EVAL_ASSERTION_JSON_SCHEMA,
    "max_length": DetectorId.EVAL_ASSERTION_MAX_LENGTH,
    "max_latency": DetectorId.EVAL_ASSERTION_MAX_LATENCY,
    "max_cost": DetectorId.EVAL_ASSERTION_MAX_COST,
}


def detector_for_assertion(assertion_type: str) -> DetectorId:
    """The detector that carries one assertion-type group. Unknown → generic."""
    return _ASSERTION_DETECTORS.get(assertion_type, DetectorId.EVAL_ASSERTION_GENERIC)


#: The seven typed outcomes an eval-evidence run terminates with (ADR-0070 §
#: consequence "a typed termination reason among seven"). Five are not errors,
#: which is the point of complete-what-succeeded: findings opened are findings
#: kept, whatever happened to the draft after them.
class TerminationReason(StrEnum):
    PROPOSAL_OPENED = "proposal_opened"
    NOTHING_FAILED = "nothing_failed"
    DRAFTER_UNAVAILABLE = "drafter_unavailable"
    RAILS_EXHAUSTED = "rails_exhausted"
    RAILS_NO_PROGRESS = "rails_no_progress"
    GATE_REJECTED = "gate_rejected"
    RATE_CAPPED = "rate_capped"


# --- ADR-0070: the drafter's bounds, in one place -----------------------------

#: Three draft attempts total: one initial and two redrafts. A self-correction
#: loop, so the cap is three — and the no-progress stop usually ends it sooner.
MAX_DRAFT_ATTEMPTS: Final = 3

#: Diff bounds. A candidate may change at most this many whole blocks and stay
#: within these length ratios — the bound that keeps the gate's floor
#: load-bearing (ADR-0068 §2's honest limit, restated for authored edits).
MAX_CHANGED_BLOCKS: Final = 4
DIFF_MIN_RATIO: Final = 0.5
DIFF_MAX_RATIO: Final = 2.0

#: The rationale is stored and disclosed as a collapsed secondary note
#: (ADR-0070 §5); bounded here and in the output model, and never the card.
RATIONALE_CHARACTERS: Final = 500

#: The per-run probe ceiling, checked BEFORE dispatch. A suite larger than this
#: is not partially gated — a partial gate is evidence about half a suite, and
#: the release flow re-measures everything once a person saves the revision.
PROBE_CASE_CAP: Final = int(os.getenv("IMPROVEMENT_PROBE_CASE_CAP", "40"))


@dataclass(frozen=True, slots=True)
class Anomaly:
    """One detector's verdict about one prompt. A FACT, never a judgement.

    ``params`` carries the arithmetic that produced it — both windows' figures,
    the ratio, the percentile — so the card can render *"truncation went from 2%
    to 31%"* without re-reading a window that has since moved. ADR-0019's rule:
    the figure keeps the row that explains it.

    **No evidence line here.** The sentence is the triage model's and arrives
    later, on the finding; an ``Anomaly`` is what the arithmetic said and must
    stay separable from what a model wrote about it, because only one of the two
    is trustworthy enough to open a row on its own.
    """

    detector_id: DetectorId
    params: dict[str, Any] = field(default_factory=dict)
    #: Eval-backed detectors set this at intake: the advisor's severity is
    #: arithmetic (share >= 0.1 is warning), and a static map cannot carry
    #: arithmetic. `None` — the every-other-detector case — falls back to
    #: :data:`DEFAULT_SEVERITY`.
    severity_override: Severity | None = None

    @property
    def severity(self) -> Severity:
        return self.severity_override or DEFAULT_SEVERITY[self.detector_id]

    @property
    def remedy_kind(self) -> RemedyKind:
        return REMEDY_KIND[self.detector_id]

    @property
    def reachable_families(self) -> tuple[RemedyFamily, ...]:
        return REACHABLE_FAMILIES.get(self.detector_id, ())


@dataclass(frozen=True, slots=True)
class WindowPair:
    """This window and the one before it, for one prompt.

    Both halves are a ``PromptCallWindow``, read through prompt-registry's
    windowed metadata seam (INT-043, ADR-0055) and typed here
    as ``Any`` only so that ``detectors`` stays importable without the ledger —
    which is what lets AC-1 run every detector as a pure function against a
    hand-built pair, with no database, no model, and no prompt body anywhere in
    the fixture.
    """

    current: Any
    prior: Any


def bounded_evidence(sentence: str) -> str:
    """The output rail, applied BEFORE STORAGE (SR-9) and not before render.

    A rail applied at render is a rail somebody bypasses with a different client.
    ``redact_evidence`` is ``prompt_readiness``'s — URL-free, markdown-link-free,
    credential-redacted — and is imported rather than copied so the two modules
    cannot end up disagreeing about what a safe sentence is.
    """
    return redact_evidence(sentence)[:MAX_EVIDENCE_CHARACTERS]

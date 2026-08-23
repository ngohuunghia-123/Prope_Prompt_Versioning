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
    "MAX_EVIDENCE_CHARACTERS",
    "PROPOSAL_TTL",
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
    "WindowPair",
    "redact_evidence",
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
}

#: **The map that bounds the model.** Which edit families an anomaly makes
#: reachable — and for every other detector, none at all.
#:
#: The model is asked to pick from the tuple this returns for the anomaly it is
#: ranking. A family outside it is dropped before storage rather than argued with,
#: which is why `triage` can accept a string from a model without that string
#: being able to become a body transform nobody sanctioned.
REACHABLE_FAMILIES: Final[dict[DetectorId, tuple[RemedyFamily, ...]]] = {
    DetectorId.PROBE_LEAK_APPEARED: (RemedyFamily.TIGHTEN_REFUSAL_BLOCK,),
    DetectorId.FALLBACK_RISING: (RemedyFamily.TIGHTEN_REFUSAL_BLOCK,),
    DetectorId.TRUNCATION_RISING: (RemedyFamily.ADD_LENGTH_RULE,),
    DetectorId.OUTPUT_RATIO_DRIFT: (RemedyFamily.ADD_BREVITY_CLAUSE,),
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
}


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

    @property
    def severity(self) -> Severity:
        return DEFAULT_SEVERITY[self.detector_id]

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

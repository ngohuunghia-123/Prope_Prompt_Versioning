"""The Usage Profile, the closed rule catalogue, and the rail on the one generated line.

**Three closed vocabularies live here and every one of them is closed on purpose.**

:class:`RuleId` is what a client renders. ADR-0053 says the client renders the
``code`` and not the ``message``, and a CI check fails the build on a rule with
no ``vi`` key — so the set has to be enumerable from Python for
``GET /api/v1/readiness/rules`` to be able to say what it is. A rule that arrived
as a bare string from a model would be a rule with no translation, no severity
and no profile clause, rendering as an empty row.

:class:`Severity` has **two** members. ADR-0067 §4 argues out why there is no
``blocker``: `evaluation` runs real assertions against real dispatches and is
warn-only (A-016), so a module whose findings are partly model-chosen cannot
defensibly be a stronger gate; and blocking on a SELF-DECLARED profile creates an
incentive to misdeclare it, which corrupts the input every rule here reads. A
third member that did nothing would be an argument for making it do something.

The four profile axes are closed because they are also four database ``CHECK``
constraints (revision 0030). A value that reaches ``registry.prompt_property``
from anywhere else is refused by the engine, and this file is what the engine's
list was written from.

**``UNDECLARED`` is a member of every axis, and it is not the same as the
conservative default.** The sentinel says *nobody answered*; :func:`resolve`
turns it into the worst case for the purpose of running rules. Keeping them
distinct is what lets the card render an *undeclared — assuming worst case*
badge honestly instead of quietly asserting that somebody called this prompt
public.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "CATALOGUE_VERSION",
    "MAX_EVIDENCE_CHARACTERS",
    "Acts",
    "Audience",
    "Finding",
    "ProbeOutcome",
    "RuleId",
    "Sensitivity",
    "Severity",
    "UntrustedInput",
    "UsageProfile",
    "lane_for_rule",
    "redact_evidence",
]

#: Bumped whenever a rule is added, retired, or has its severity or admitting
#: clause changed. Stored on every frozen ``readiness.report`` so a report stays
#: explicable after the catalogue moves — the same reason ``call_record`` stores
#: ``price_row_id`` beside its cost (ADR-0019), and the reason AC-7 can assert
#: that a bump does not disturb a report already written.
CATALOGUE_VERSION: Final = "1"

#: SR-7's application-side cap. ``ck_readiness_probe_case_result_detail_is_bounded``
#: is the database's copy of the same number, deliberately looser, because a
#: backstop that fires at the same threshold as the rail can never tell you the
#: rail was skipped.
MAX_EVIDENCE_CHARACTERS: Final = 400


class Audience(StrEnum):
    """Who can reach this prompt at all. Deck 5 slide 11, slide 54."""

    UNDECLARED = "undeclared"
    INTERNAL = "internal"
    AUTHENTICATED_USER = "authenticated_user"
    PUBLIC = "public"


class UntrustedInput(StrEnum):
    """What content the prompt's context absorbs. Deck 5 slide 22, slide 25."""

    UNDECLARED = "undeclared"
    NONE = "none"
    USER_TEXT = "user_text"
    RETRIEVED = "retrieved"
    THIRD_PARTY = "third_party"


class Acts(StrEnum):
    """What the output can cause to happen. Deck 5 slide 11, slide 54."""

    UNDECLARED = "undeclared"
    ANSWERS_ONLY = "answers_only"
    EMITS_TOOL_CALLS = "emits_tool_calls"
    IRREVERSIBLE = "irreversible"


class Sensitivity(StrEnum):
    """What class of data is in play. Deck 6 slide 86."""

    UNDECLARED = "undeclared"
    SYNTHETIC = "synthetic"
    BUSINESS = "business"
    PERSONAL_DATA = "personal_data"


class Severity(StrEnum):
    """Two members. See the module docstring, and ADR-0067 §4.

    Nothing in this module blocks registration, save, submit or release, and the
    absence of a third value is what keeps that true when somebody is in a hurry.
    """

    ADVICE = "advice"
    WARNING = "warning"


class ProbeOutcome(StrEnum):
    """What one probe case did.

    ``ERROR`` is separate from both, and the separation is load-bearing: a
    provider timeout is not a guardrail win. Folding it into ``REFUSED`` would
    make an outage read as a perfect score, which is the one wrong answer a
    readiness card must never give.
    """

    REFUSED = "refused"
    LEAKED = "leaked"
    ERROR = "error"


class RuleId(StrEnum):
    """The closed catalogue. Every member needs a ``vi`` key or CI fails (AC-4).

    Grouped by the lane that raises it, because the lane decides what evidence is
    behind the finding — and that is the thing a reader most needs to know before
    deciding whether to act on it.
    """

    # --- Lane A, static: no model, no dispatch, free, always ------------------
    #: A `{{variable}}` sits inside an `<instructions>` block, so untrusted text
    #: substituted into it is read as instruction rather than as data. Deck 5
    #: slide 38's spotlighting, and the only Lane A rule with a parser-derived
    #: remedy attached (D-05).
    INTERPOLATION_INSIDE_INSTRUCTIONS = "interpolation_inside_instructions"
    #: Text that LOOKS like a placeholder and is not one — `{name}`, `${name}`,
    #: `{{ name }}` with an illegal character in it. `prompt_composition.render`
    #: substitutes only what `PLACEHOLDER` matches, so the rest reaches the model
    #: as literal braces. Read from that same regex, so this rule cannot disagree
    #: with what production actually does.
    PLACEHOLDER_WILL_NOT_SUBSTITUTE = "placeholder_will_not_substitute"
    #: No `<instructions>` block at all, or blocks in an order that puts context
    #: after the instruction that interprets it.
    CANONICAL_STRUCTURE_WEAK = "canonical_structure_weak"
    #: The prompt has no eval suite. Advice, not warning, and never a block:
    #: A-062 runs every suite at submit, and a prompt with none passes trivially.
    NO_EVAL_COVERAGE = "no_eval_coverage"
    #: A suite exists and is thin enough that passing it says little.
    THIN_EVAL_COVERAGE = "thin_eval_coverage"
    #: **The one that outranks everything else on the card.** Private data plus
    #: untrusted content plus an outward act — deck 5 slide 41. Computable from a
    #: declaration rather than guessed, which is the whole argument for the
    #: profile existing. Printed in full even when previously dismissed.
    LETHAL_TRIFECTA = "lethal_trifecta"
    #: The body's own token cost, before any input or output. Always advice.
    BODY_COST = "body_cost"
    #: Nobody has declared the profile, so every rule above ran against the
    #: conservative worst case. Advice, and it is the only rule that names the
    #: fix as a dropdown rather than an edit.
    PROFILE_UNDECLARED = "profile_undeclared"

    # --- Lane C, probe: a measurement, on the workspace's credential ----------
    #: `n of m` shipped injection cases were not refused. A NUMBER, not an
    #: opinion — the difference ADR-0067 is named for.
    PROBE_INJECTION_LEAKED = "probe_injection_leaked"
    #: `n of m` shipped leakage cases printed part of the system prompt back.
    PROBE_SYSTEM_PROMPT_LEAKED = "probe_system_prompt_leaked"
    #: The probe could not complete — dispatch errors, not guardrail failures.
    PROBE_INCOMPLETE = "probe_incomplete"

    # --- Lane B, drafted: the closed set no test can express ------------------
    #: Two instructions in the body that cannot both be followed.
    CONTRADICTORY_INSTRUCTIONS = "contradictory_instructions"
    #: The body says the same thing twice at length, which costs tokens on every
    #: single call and buys nothing.
    REDUNDANT_BODY = "redundant_body"
    #: The body tells the model what to do and never what to do when it cannot —
    #: no refusal path, so the failure mode is invention.
    NO_REFUSAL_PATH = "no_refusal_path"


@dataclass(frozen=True, slots=True)
class UsageProfile:
    """Four declared axes. Read from prompt-registry; never written here.

    ``writes_tables_it_does_not_own: none`` — this module reads the profile and
    prompt-registry owns the column (revision 0030).
    """

    audience: Audience = Audience.UNDECLARED
    untrusted_input: UntrustedInput = UntrustedInput.UNDECLARED
    acts: Acts = Acts.UNDECLARED
    sensitivity: Sensitivity = Sensitivity.UNDECLARED

    @property
    def is_declared(self) -> bool:
        """True when a person has answered every axis.

        All four, not any: a partly declared profile still has an axis being
        resolved to its worst case, and the badge that says so has to appear
        while that is true.
        """
        return all(
            value != "undeclared"
            for value in (self.audience, self.untrusted_input, self.acts, self.sensitivity)
        )

    def resolve(self) -> "UsageProfile":
        """The profile the rules actually run against — worst case for anything undeclared.

        Conservative by default, and loud about it rather than silent. A default
        plus a one-dropdown correction is a trade a person makes gladly: the
        correction is made once and permanently silences a class of finding. A
        *guess* has to be argued with every time (A-163).
        """
        return UsageProfile(
            audience=Audience.PUBLIC if self.audience == Audience.UNDECLARED else self.audience,
            untrusted_input=(
                UntrustedInput.THIRD_PARTY
                if self.untrusted_input == UntrustedInput.UNDECLARED
                else self.untrusted_input
            ),
            acts=Acts.IRREVERSIBLE if self.acts == Acts.UNDECLARED else self.acts,
            sensitivity=(
                Sensitivity.PERSONAL_DATA
                if self.sensitivity == Sensitivity.UNDECLARED
                else self.sensitivity
            ),
        )

    def as_dict(self) -> dict[str, str]:
        """The stored shape. Used for ``report.profile_snapshot`` and the wire."""
        return {
            "audience": str(self.audience),
            "untrusted_input": str(self.untrusted_input),
            "acts": str(self.acts),
            "sensitivity": str(self.sensitivity),
        }

    @classmethod
    def from_row(cls, row: Any) -> "UsageProfile":
        """Build from anything with the four attributes or the four keys.

        Tolerant of a mapping or an object because it is fed both — a registry
        row on one path and a stored ``profile_snapshot`` on the other — and a
        second constructor would be a second place for the axis names to drift.
        """
        get = row.get if hasattr(row, "get") else lambda key, default: getattr(row, key, default)
        return cls(
            audience=Audience(get("audience", "undeclared") or "undeclared"),
            untrusted_input=UntrustedInput(get("untrusted_input", "undeclared") or "undeclared"),
            acts=Acts(get("acts", "undeclared") or "undeclared"),
            sensitivity=Sensitivity(get("sensitivity", "undeclared") or "undeclared"),
        )


@dataclass(frozen=True, slots=True)
class Finding:
    """One row on the card.

    ``params`` carries the numbers the ``vi`` catalogue interpolates — *"{leaked}
    of {total} injection cases were not refused"* — so the sentence is
    translated and the figures are not.

    ``admitted_by`` names the profile clause that let this finding through. It is
    on the finding rather than in a lookup table because a reader's first
    question about an unwelcome finding is *why am I being told this*, and the
    answer has to travel with the row that provoked it.

    ``evidence`` is the ONE generated line and the ONE i18n exemption (D-09). It
    is generated directly in Vietnamese — no English intermediate, because a
    translation step is a second model call on the display path — and it has
    passed :func:`redact_evidence` **before storage**, not before render.
    """

    rule_id: RuleId
    severity: Severity
    params: dict[str, Any] = field(default_factory=dict)
    admitted_by: str = ""
    evidence: str = ""
    #: A parser-derived replacement body, or None. Only ever set by a Lane A rule
    #: with a definition of correct that does not require running the prompt
    #: (D-05) — never by Lane B, at any confidence.
    proposed_body: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": str(self.rule_id),
            "severity": str(self.severity),
            "params": self.params,
            "admitted_by": self.admitted_by,
            "evidence": self.evidence,
            "has_proposed_body": self.proposed_body is not None,
        }


#: The rail's blocklist. Each pattern is here because the evidence line is the
#: one place in this module where text derived from a hostile prompt body could
#: reach a colleague's screen, and each removes a different way of using that.
#: Two alternatives, because two URL shapes matter and only one of them has a
#: `//`. `data:` and `javascript:` are opaque-path schemes — `data:text/html;...`
#: carries a whole document with no slashes in the scheme part at all — and a
#: pattern demanding `://` lets both straight through. That gap was found by
#: `tests/security/test_readiness_evidence_line_survives_its_rail.py` rather than
#: by reading, which is the argument for parameterising that test over SHAPES
#: rather than over one example.
_URL = re.compile(
    r"\b(?:https?|ftp|file)://\S+|\b(?:data|javascript|vbscript):\S+", re.IGNORECASE
)
_MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]{1,200}>")
#: Credential shapes: anything long and key-like, plus this product's own
#: `prope_key_` prefix and the common provider prefixes. Matched on shape rather
#: than on a list, because the list is always one provider out of date.
_CREDENTIAL = re.compile(
    r"\b(?:prope_key_[A-Za-z0-9_\-]+|sk-[A-Za-z0-9_\-]{16,}|[A-Za-z0-9_\-]{40,})\b"
)

_REDACTED: Final = "[đã ẩn]"


def redact_evidence(text: str) -> str:
    """SR-7. Run **before storage**, never at render.

    A rail applied at render is a rail somebody bypasses with a different client
    — and this product's API is the contract, not its SPA. Storing the redacted
    form means every reader gets the same string and there is no code path left
    where the raw one is still available to leak.

    Order matters: markdown links are collapsed before bare URLs, because a
    ``[text](url)`` whose URL was already replaced would leave a link with a
    redaction marker in it that still renders as a link. Tags go last, so that
    anything the earlier passes turned into angle brackets is caught too.
    """
    cleaned = _MARKDOWN_LINK.sub(_REDACTED, text)
    cleaned = _URL.sub(_REDACTED, cleaned)
    cleaned = _CREDENTIAL.sub(_REDACTED, cleaned)
    cleaned = _HTML_TAG.sub(" ", cleaned)
    # Newlines collapse: the card gives a finding one line, and a body that
    # supplied fifty would push every other finding off the screen.
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > MAX_EVIDENCE_CHARACTERS:
        cleaned = cleaned[: MAX_EVIDENCE_CHARACTERS - 1].rstrip() + "…"
    return cleaned


#: Which lane raises each rule. Rendered by ``GET /api/v1/readiness/rules`` so a
#: reader can tell a MEASUREMENT from an opinion before deciding how much weight
#: to give it — which is the distinction ADR-0067 is named for, made visible on
#: the one screen where it changes what somebody does next.
_LANE: Final[dict[RuleId, str]] = {
    RuleId.PROBE_INJECTION_LEAKED: "probe",
    RuleId.PROBE_SYSTEM_PROMPT_LEAKED: "probe",
    RuleId.PROBE_INCOMPLETE: "probe",
    RuleId.CONTRADICTORY_INSTRUCTIONS: "drafted",
    RuleId.REDUNDANT_BODY: "drafted",
    RuleId.NO_REFUSAL_PATH: "drafted",
}


def lane_for_rule(rule_id: RuleId) -> str:
    """``"static" | "probe" | "drafted"``.

    Defaults to ``static`` rather than to ``unknown``: a rule with no entry is a
    Lane A rule, because Lane A is the lane a rule joins by simply existing, and
    an ``unknown`` on a client legend would be a shrug where a fact belongs.
    """
    return _LANE.get(rule_id, "static")

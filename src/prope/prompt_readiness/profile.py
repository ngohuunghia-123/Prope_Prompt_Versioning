"""The profile filter. The one file that makes this module not a lint.

**Generate first, drop second, and count the drop.** A rule could equally well be
skipped before it runs — cheaper, and it would produce an identical card. It is
not, and the reason is the metric: ``findings_suppressed_total{rule_id, axis}``
is the number that proves the Usage Profile earns the migration that added it. If
that counter sits near zero, the profile is decoration and D-02 was wrong, and
there is no way to learn that from a filter that skipped silently.

It also gives AC-1 something to assert. A filter that generated nothing to begin
with passes a test written against the returned list and fails one written
against the counter, which is why the test is written against the counter.

**Each rule declares the profiles that ADMIT it, not the ones that suppress it.**
The positive form is the one a reviewer can read, and it fails safe in the right
direction: a rule added with no clause admits nothing and shows up as a rule
nobody ever sees, which is a bug somebody notices. The inverse — a rule with no
suppression clause firing at everybody always — is the noise this module exists
to avoid, and it is invisible in exactly the workspaces where it does most harm.
"""

from collections.abc import Callable, Iterable, Sequence
from typing import Final

from prope.prompt_readiness.domain import (
    Acts,
    Finding,
    RuleId,
    Sensitivity,
    UntrustedInput,
    UsageProfile,
)
from prope.prompt_readiness.observability import findings_suppressed_total, findings_total

__all__ = ["ADMISSION", "admits", "apply_profile", "reason_for"]


#: ``(profile) -> bool``, one per rule, over the RESOLVED profile.
#: Written as data rather than as branches inside each rule so that
#: ``GET /api/v1/readiness/rules`` can render the clause, the card can print it
#: as ``admitted_by``, and a test can walk the table. A rule whose clause lived
#: inside its own function body would be a clause nobody outside that function
#: could quote back to the person asking *why am I being told this*.
ADMISSION: Final[dict[RuleId, Callable[[UsageProfile], bool]]] = {
    # Spotlighting matters exactly when something untrusted is substituted. A
    # prompt whose only variables come from the product's own configuration is
    # not made safer by moving them out of `<instructions>`, and telling its
    # author otherwise is the false positive this module is named for.
    RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS: lambda p: p.untrusted_input != UntrustedInput.NONE,
    # Always. Braces that will not substitute reach the model as literal text
    # whoever is calling and whatever the prompt is for — there is no exposure
    # under which `{customer_name}` is what the author meant to send.
    RuleId.PLACEHOLDER_WILL_NOT_SUBSTITUTE: lambda p: True,
    RuleId.CANONICAL_STRUCTURE_WEAK: lambda p: True,
    # Coverage is advice for a prompt with no exposure and a warning for one
    # that acts. The rule fires for everyone; `severity_for` below is where the
    # profile changes its weight rather than its existence, because "you have no
    # tests" is true regardless and only its urgency moves.
    RuleId.NO_EVAL_COVERAGE: lambda p: True,
    RuleId.THIN_EVAL_COVERAGE: lambda p: True,
    # The one that outranks everything. All three legs, over the DECLARED
    # profile — deck 5 slide 41.
    RuleId.LETHAL_TRIFECTA: lambda p: (
        p.sensitivity in (Sensitivity.BUSINESS, Sensitivity.PERSONAL_DATA)
        and p.untrusted_input
        in (UntrustedInput.USER_TEXT, UntrustedInput.RETRIEVED, UntrustedInput.THIRD_PARTY)
        and p.acts in (Acts.EMITS_TOOL_CALLS, Acts.IRREVERSIBLE)
    ),
    RuleId.BODY_COST: lambda p: True,
    RuleId.PROFILE_UNDECLARED: lambda p: True,
    # A probe result is a measurement that was asked for and paid for. Filtering
    # it on the profile would be discarding evidence somebody bought — the
    # profile already chose which sets ran.
    RuleId.PROBE_INJECTION_LEAKED: lambda p: True,
    RuleId.PROBE_SYSTEM_PROMPT_LEAKED: lambda p: True,
    RuleId.PROBE_INCOMPLETE: lambda p: True,
    # Lane B's three. Contradictions and redundancy are true of a body whatever
    # it is for. A missing refusal path is not: a prompt that answers only, from
    # trusted input, has nothing to refuse.
    RuleId.CONTRADICTORY_INSTRUCTIONS: lambda p: True,
    RuleId.REDUNDANT_BODY: lambda p: True,
    RuleId.NO_REFUSAL_PATH: lambda p: (
        p.untrusted_input != UntrustedInput.NONE or p.acts != Acts.ANSWERS_ONLY
    ),
}

#: Which axis to blame when a rule is suppressed, for the metric's label. One
#: axis per rule and not a set: a label that could hold four values in
#: combination is a cardinality problem wearing a diagnostic's clothes (deck 6
#: slide 54), and the axis named here is the one whose value did the suppressing.
_BLAMED_AXIS: Final[dict[RuleId, str]] = {
    RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS: "untrusted_input",
    RuleId.LETHAL_TRIFECTA: "trifecta",
    RuleId.NO_REFUSAL_PATH: "acts",
}

#: Human-readable, in the sense that the CLIENT renders it from a key. This is
#: the key stem, not the sentence — ADR-0053 stands, and the ``vi`` catalogue
#: carries ``readiness.admitted.<stem>``.
_ADMISSION_STEM: Final[dict[RuleId, str]] = {
    RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS: "untrusted_input_present",
    RuleId.LETHAL_TRIFECTA: "all_three_legs",
    RuleId.NO_REFUSAL_PATH: "can_act_or_absorbs_untrusted",
}


def admits(rule_id: RuleId, profile: UsageProfile) -> bool:
    """Does this profile admit this rule?

    An unknown rule admits **nothing**. It cannot be rendered — there is no
    ``vi`` key for a code the catalogue does not contain — so admitting it would
    put an empty row on somebody's screen, and SR-9 drops unknown codes before
    render for that reason. Failing closed here means the same decision is made
    once, in the place that already knows the catalogue.
    """
    clause = ADMISSION.get(rule_id)
    if clause is None:
        return False
    return clause(profile.resolve())


def reason_for(rule_id: RuleId) -> str:
    """The ``admitted_by`` stem for a finding, or ``"always"``.

    ``"always"`` rather than an empty string: a blank would render as a missing
    clause and invite somebody to go looking for one, when the honest answer is
    that this rule does not depend on the profile at all.
    """
    return _ADMISSION_STEM.get(rule_id, "always")


def apply_profile(findings: Iterable[Finding], profile: UsageProfile, *, trigger: str) -> Sequence[Finding]:
    """Drop what the profile does not admit, and COUNT every drop.

    Returns the surviving findings with ``admitted_by`` filled in. The trifecta
    finding is sorted to the front unconditionally: it is the one finding that
    outranks everything else on the card, and a card that buried it under six
    pieces of advice would be the alert fatigue this module measures in other
    people's rules.
    """
    kept: list[Finding] = []
    for finding in findings:
        if not admits(finding.rule_id, profile):
            findings_suppressed_total.labels(
                rule_id=str(finding.rule_id),
                axis=_BLAMED_AXIS.get(finding.rule_id, "unknown_rule"),
            ).inc()
            continue
        findings_total.labels(
            rule_id=str(finding.rule_id),
            severity=str(finding.severity),
            trigger=trigger,
        ).inc()
        kept.append(
            Finding(
                rule_id=finding.rule_id,
                severity=finding.severity,
                params=finding.params,
                admitted_by=reason_for(finding.rule_id),
                evidence=finding.evidence,
                proposed_body=finding.proposed_body,
            )
        )

    kept.sort(key=lambda f: (f.rule_id != RuleId.LETHAL_TRIFECTA, f.severity != "warning"))
    return tuple(kept)

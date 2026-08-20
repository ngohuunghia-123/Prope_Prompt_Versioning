"""AC-1 and AC-8 — the Usage Profile is the differentiator, asserted over the counter.

**AC-1 is written against ``findings_suppressed_total`` and not against the
returned list**, and that is the whole point of the test. A profile filter that
skipped a rule *before* running it would produce an identical card and leave the
counter at zero, and there is no way to tell those two implementations apart from
the outside. The counter is what proves generation happened and a drop followed —
which is the property the lock calls *suppression is the proof*: if that number
sits near zero in production, the profile is decoration and D-02 was wrong.

**AC-8 is the user's own example, turned into an assertion.** An internal-only
prompt must not be told it lacks a guardrail meant for public users; the same
body declared public must be. Every competitor lints context-free, and a
context-free lint is right often enough to be installed and wrong often enough to
be ignored — this test is the line between the two.
"""

from prometheus_client import REGISTRY

from prope.prompt_readiness.domain import (
    Acts,
    Audience,
    RuleId,
    Sensitivity,
    Severity,
    UntrustedInput,
    UsageProfile,
)
from prope.prompt_readiness.profile import ADMISSION, admits, apply_profile
from prope.prompt_readiness.rules import StaticInputs, run_static_lane

#: A body that trips the spotlighting rule: a variable inside `<instructions>`.
#: Deliberately the SAME body in both halves of AC-8 — the finding has to move
#: because the declaration moved, not because the prompt did.
BODY = (
    "<system>Bạn là trợ lý hỗ trợ.</system>"
    "<instructions>Trả lời câu hỏi sau: {{cau_hoi}}</instructions>"
)

INTERNAL = UsageProfile(
    audience=Audience.INTERNAL,
    untrusted_input=UntrustedInput.NONE,
    acts=Acts.ANSWERS_ONLY,
    sensitivity=Sensitivity.SYNTHETIC,
)

PUBLIC = UsageProfile(
    audience=Audience.PUBLIC,
    untrusted_input=UntrustedInput.THIRD_PARTY,
    acts=Acts.IRREVERSIBLE,
    sensitivity=Sensitivity.PERSONAL_DATA,
)


def _suppressed(rule_id: RuleId, axis: str) -> float:
    """The counter, or 0.0 — ``get_sample_value`` answers ``None`` for untouched labels."""
    value = REGISTRY.get_sample_value(
        "prope_readiness_findings_suppressed_total",
        {"rule_id": str(rule_id), "axis": axis},
    )
    return value or 0.0


def test_the_filter_drops_after_generation_and_counts_the_drop() -> None:
    """AC-1. The counter moves, which is what proves the finding was generated."""
    before = _suppressed(RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS, "untrusted_input")

    generated = run_static_lane(StaticInputs(body=BODY, profile=INTERNAL))
    assert RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS in {f.rule_id for f in generated}, (
        "the rule must FIRE for an internal prompt and be dropped by the filter afterwards; "
        "a rule that never fired would leave the suppression counter at zero and make the "
        "Usage Profile unfalsifiable"
    )

    kept = apply_profile(generated, INTERNAL, trigger="edit")
    assert RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS not in {f.rule_id for f in kept}

    after = _suppressed(RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS, "untrusted_input")
    assert after == before + 1


def test_the_same_body_is_judged_differently_by_its_declaration() -> None:
    """AC-8. The user's own example: internal-only is not lectured about guardrails."""
    internal = {f.rule_id for f in apply_profile(run_static_lane(StaticInputs(body=BODY, profile=INTERNAL)), INTERNAL, trigger="edit")}
    public = {f.rule_id for f in apply_profile(run_static_lane(StaticInputs(body=BODY, profile=PUBLIC)), PUBLIC, trigger="edit")}

    assert RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS not in internal
    assert RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS in public

    # The trifecta is the sharper half of the same claim: it is computed from the
    # DECLARATION and from nothing else, so it cannot appear for a prompt whose
    # author said there is no untrusted input and no outward act.
    assert RuleId.LETHAL_TRIFECTA not in internal
    assert RuleId.LETHAL_TRIFECTA in public


def test_the_trifecta_finding_sorts_first() -> None:
    """It outranks everything else on the card, so it cannot be buried under advice."""
    kept = apply_profile(run_static_lane(StaticInputs(body=BODY, profile=PUBLIC)), PUBLIC, trigger="edit")
    assert kept[0].rule_id is RuleId.LETHAL_TRIFECTA


def test_every_rule_in_the_catalogue_has_an_admission_clause() -> None:
    """A rule with no clause admits nothing, and would be invisible in production.

    Failing closed is the right default — see ``profile.admits`` — but a rule that
    silently never renders is a rule somebody wrote and nobody reads, so the
    absence is caught here rather than by a person wondering where it went.
    """
    missing = [rule for rule in RuleId if rule not in ADMISSION]
    assert missing == [], f"rules with no admission clause would never render: {missing}"


def test_an_unknown_rule_is_admitted_by_nothing() -> None:
    """SR-9's shape at the filter. A code outside the catalogue cannot be rendered."""
    assert admits("not_a_rule", PUBLIC) is False  # type: ignore[arg-type]


def test_no_severity_above_warning_exists() -> None:
    """ADR-0067 §4. There is no `blocker`, and a third member is the whole risk.

    A value that does nothing is an argument for making it do something, filled in
    later by whoever is in a hurry — so the absence is asserted rather than
    intended, in the same file as the rules it would have applied to.
    """
    assert [member.value for member in Severity] == ["advice", "warning"]

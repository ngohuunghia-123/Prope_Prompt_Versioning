"""AC-6 and the Lane A rules, over hand-written bodies. No database, no model, no provider.

Lane A is pure by construction — ``run_static_lane`` takes one dataclass and
returns findings — and this file is what that buys: the whole lane exercised in
milliseconds, so the rules can be argued with in a test rather than in
production.

**AC-6 is the sharp one.** A parser-derived edit is the only body change this
module may propose (D-05, SR-10), and it is allowed only because *"move this
variable out of the instruction block"* has a definition of correct that does not
require running the prompt. That definition is exactly what is asserted here: the
result still parses as canonical XML and the declared-variable set is
byte-identical. A remedy that changed which variables a body needs would break
every caller of the prompt at render time, silently, which is worse than the
finding it fixed.
"""

from prope.canonical_prompt import validate_canonical_xml
from prope.prompt_composition import required_variables
from prope.prompt_readiness.domain import (
    Acts,
    Audience,
    RuleId,
    Sensitivity,
    Severity,
    UntrustedInput,
    UsageProfile,
)
from prope.prompt_readiness.rules import THIN_SUITE_CASES, StaticInputs, run_static_lane

PUBLIC = UsageProfile(
    audience=Audience.PUBLIC,
    untrusted_input=UntrustedInput.USER_TEXT,
    acts=Acts.ANSWERS_ONLY,
    sensitivity=Sensitivity.BUSINESS,
)


def _rules(body: str, **kwargs: object) -> dict[RuleId, object]:
    findings = run_static_lane(StaticInputs(body=body, profile=PUBLIC, **kwargs))  # type: ignore[arg-type]
    return {finding.rule_id: finding for finding in findings}


def test_a_variable_on_its_own_line_moves_and_the_body_still_parses() -> None:
    """AC-6. Canonical XML in, canonical XML out, identical declared variables."""
    body = (
        "<system>Bạn là trợ lý.</system>"
        "<context>Khách hàng đang hỏi.</context>"
        "<instructions>\nCâu hỏi:\n{{cau_hoi}}\nTrả lời ngắn gọn.\n</instructions>"
    )
    finding = _rules(body)[RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS]
    proposed = finding.proposed_body  # type: ignore[attr-defined]

    assert proposed is not None
    validate_canonical_xml(proposed)
    assert required_variables(proposed) == required_variables(body)
    # And the point of the move: the placeholder is no longer inside the block
    # whose content is read at instruction priority.
    assert "{{cau_hoi}}" not in proposed.split("<instructions>")[1].split("</instructions>")[0]


def test_a_variable_mid_sentence_is_reported_and_not_rewritten() -> None:
    """D-05's boundary. Relocating a sentence is a semantic act and is refused.

    The finding still fires — the risk is real either way — and it simply arrives
    without an edit attached. That asymmetry is the whole of D-05: the remedy is
    withheld where correctness would need a judgement, not where the problem is
    smaller.
    """
    body = (
        "<system>Bạn là trợ lý.</system>"
        "<instructions>Hãy trả lời câu hỏi {{cau_hoi}} theo đúng chính sách hoàn tiền "
        "đã được duyệt và luôn giữ giọng lịch sự với khách hàng.</instructions>"
    )
    finding = _rules(body)[RuleId.INTERPOLATION_INSIDE_INSTRUCTIONS]
    assert finding.proposed_body is None  # type: ignore[attr-defined]


def test_near_miss_braces_are_reported_because_they_reach_the_model_verbatim() -> None:
    """`render` substitutes what PLACEHOLDER matches and nothing else."""
    body = "<system>Chào {ten_khach}, tôi là ${bot_name}.</system><instructions>Trả lời.</instructions>"
    finding = _rules(body)[RuleId.PLACEHOLDER_WILL_NOT_SUBSTITUTE]
    assert finding.severity is Severity.WARNING  # type: ignore[attr-defined]
    assert finding.params["count"] == 2  # type: ignore[attr-defined]


def test_a_well_formed_placeholder_is_not_reported() -> None:
    """The regex is `prompt_composition`'s own, so this cannot disagree with production."""
    body = "<system>Chào {{ten_khach}}.</system><instructions>Trả lời.</instructions>"
    assert RuleId.PLACEHOLDER_WILL_NOT_SUBSTITUTE not in _rules(body)


def test_blocks_out_of_reading_order_are_reported() -> None:
    """An instruction that interprets context the model has not read is read twice or not at all."""
    body = "<instructions>Dựa vào ngữ cảnh, trả lời.</instructions><context>Khách VIP.</context>"
    finding = _rules(body)[RuleId.CANONICAL_STRUCTURE_WEAK]
    assert "out_of_order" in finding.params["problems"]  # type: ignore[attr-defined]


def test_a_body_with_no_instructions_is_reported() -> None:
    body = "<system>Bạn là trợ lý.</system><context>Khách VIP.</context>"
    finding = _rules(body)[RuleId.CANONICAL_STRUCTURE_WEAK]
    assert "no_instructions" in finding.params["problems"]  # type: ignore[attr-defined]


def test_coverage_severity_moves_with_exposure_and_existence_does_not() -> None:
    """*"You have no tests"* is true whatever the prompt is for; only urgency moves.

    Suppressing the rule for an internal prompt would leave its author with no
    prompt at all to add coverage they might still want, so the rule fires for
    everyone and the profile changes its weight instead.
    """
    body = "<system>Bạn là trợ lý.</system><instructions>Trả lời.</instructions>"

    exposed = _rules(body)[RuleId.NO_EVAL_COVERAGE]
    assert exposed.severity is Severity.WARNING  # type: ignore[attr-defined]

    internal = UsageProfile(
        audience=Audience.INTERNAL,
        untrusted_input=UntrustedInput.NONE,
        acts=Acts.ANSWERS_ONLY,
        sensitivity=Sensitivity.SYNTHETIC,
    )
    quiet = {
        finding.rule_id: finding
        for finding in run_static_lane(StaticInputs(body=body, profile=internal))
    }
    assert quiet[RuleId.NO_EVAL_COVERAGE].severity is Severity.ADVICE


def test_a_thin_suite_is_reported_and_a_full_one_is_not() -> None:
    body = "<system>Bạn là trợ lý.</system><instructions>Trả lời.</instructions>"
    assert RuleId.THIN_EVAL_COVERAGE in _rules(body, suite_count=1, case_count=2)
    assert RuleId.THIN_EVAL_COVERAGE not in _rules(
        body, suite_count=1, case_count=THIN_SUITE_CASES
    )


def test_an_undeclared_profile_is_badged_rather_than_guessed() -> None:
    """A-163. The card says which axes are missing and what it assumed instead."""
    body = "<system>Bạn là trợ lý.</system><instructions>Trả lời.</instructions>"
    findings = {
        finding.rule_id: finding
        for finding in run_static_lane(StaticInputs(body=body, profile=UsageProfile()))
    }
    finding = findings[RuleId.PROFILE_UNDECLARED]
    assert sorted(finding.params["missing"]) == [
        "acts",
        "audience",
        "sensitivity",
        "untrusted_input",
    ]
    assert finding.params["assumed"] == {
        "audience": "public",
        "untrusted_input": "third_party",
        "acts": "irreversible",
        "sensitivity": "personal_data",
    }


def test_a_body_that_will_not_parse_produces_no_finding_and_does_not_raise() -> None:
    """Registry refuses an unparseable body before it can be saved.

    A second refusal here would be a finding about a state that cannot reach this
    code, and raising would turn a card read into a 500 for a revision somebody
    can see on their screen.
    """
    findings = run_static_lane(StaticInputs(body="<system>unclosed", profile=PUBLIC))
    assert RuleId.CANONICAL_STRUCTURE_WEAK not in {finding.rule_id for finding in findings}

"""A-005's deterministic assertions, A-061's registry, and the two failures that
must never read as a fail.

**Pass/fail comes only from these.** There is no LLM judge, no embedding
similarity and no model-scored quality anywhere in this module — 00_context.md's
anti-goals put that out, and this is the file where it would have arrived.

The registry is keyed by the suite's declared OUTPUT MODALITY rather than being
one flat list, which is A-061: a `structured` suite can only assert on the SHAPE
of what came back — that an asset arrived, of what type, how many, how fast — and
`exact` or `substring` against an asset reference is not a weaker check, it is a
meaningless one.

**Two things are errors and not fails, and the distinction is A-057's.** A regex
that times out and an assertion this module cannot evaluate are failures of the
assertion MACHINERY, not evidence about a prompt — the same rule that already
keeps an unreachable provider from reading as a bad revision.
"""

import time
from decimal import Decimal

import pytest

from prope.evaluation.assertions import (
    ASSET_SCHEMES,
    AssertionTimeout,
    AssertionUnevaluable,
    CaseObservation,
    check_modality,
    compile_assertions,
    evaluate,
    evaluate_all,
    parse_assertions,
    returned_shape,
)
from prope.evaluation.domain import (
    ASSERTION_TYPES_BY_MODALITY,
    REGEX_TIMEOUT_SECONDS,
    AssertionPatternInvalid,
    AssertionSpec,
    AssertionType,
    ModalityMismatch,
    OutputModality,
)

TEXT = OutputModality.TEXT

STRUCTURED = OutputModality.STRUCTURED


def _observe(content: str | None, **kwargs) -> CaseObservation:
    return CaseObservation(content=content, **kwargs)


def _spec(assertion_type: AssertionType, value=None) -> AssertionSpec:
    return AssertionSpec(type=assertion_type, value=value)


# --- the registry itself ---------------------------------------------------


def test_the_registry_is_keyed_by_modality_and_the_two_sets_differ() -> None:
    """A-061. If the two sets were equal the key would be decoration."""
    text_types = ASSERTION_TYPES_BY_MODALITY[TEXT]
    structured_types = ASSERTION_TYPES_BY_MODALITY[STRUCTURED]

    assert text_types != structured_types
    assert AssertionType.SUBSTRING in text_types
    assert AssertionType.SUBSTRING not in structured_types
    assert AssertionType.ASSET_COUNT in structured_types
    assert AssertionType.ASSET_COUNT not in text_types

    # The three that reach BOTH: a JSON schema, a latency bound and a cost
    # bound are properties of any response whatever its modality.
    assert text_types & structured_types == {
        AssertionType.JSON_SCHEMA,
        AssertionType.MAX_LATENCY,
        AssertionType.MAX_COST,
    }


def test_every_registered_type_has_an_evaluator_in_both_directions() -> None:
    """A type in the registry with no evaluator would raise a KeyError at run
    time — inside `worker`, on a paid case — and an evaluator with no registry
    entry is a check nobody can author."""
    from prope.evaluation.assertions import EVALUATORS

    registered = set(ASSERTION_TYPES_BY_MODALITY[TEXT] | ASSERTION_TYPES_BY_MODALITY[STRUCTURED])

    assert registered == set(EVALUATORS)
    assert registered == set(AssertionType)


def test_a_type_outside_the_suites_modality_is_unevaluable_rather_than_a_fail() -> None:
    """It cannot be reached through the API — `compile_assertions` refuses it at
    authoring — so reaching it means a row was written another way, and the
    honest answer is an error rather than a verdict about the prompt."""
    with pytest.raises(AssertionUnevaluable):
        evaluate(_spec(AssertionType.SUBSTRING, "x"), _observe("x"), STRUCTURED)


# --- the eight text evaluators ---------------------------------------------


@pytest.mark.parametrize(
    ("spec", "content", "expected"),
    [
        (_spec(AssertionType.EXACT, "hello"), "hello", True),
        (_spec(AssertionType.EXACT, "hello"), "hello ", False),
        (_spec(AssertionType.SUBSTRING, "ell"), "hello", True),
        (_spec(AssertionType.SUBSTRING, "xyz"), "hello", False),
        (_spec(AssertionType.REGEX, r"^h.llo$"), "hello", True),
        (_spec(AssertionType.REGEX, r"^\d+$"), "hello", False),
        (_spec(AssertionType.REQUIRED_PHRASE, ["a", "b"]), "a and b", True),
        (_spec(AssertionType.REQUIRED_PHRASE, ["a", "z"]), "a and b", False),
        (_spec(AssertionType.FORBIDDEN_PHRASE, ["z"]), "a and b", True),
        (_spec(AssertionType.FORBIDDEN_PHRASE, ["b"]), "a and b", False),
        (_spec(AssertionType.MAX_LENGTH, 5), "hello", True),
        (_spec(AssertionType.MAX_LENGTH, 4), "hello", False),
    ],
)
def test_the_text_evaluators_answer_pass_or_fail(spec, content, expected) -> None:
    assert evaluate(spec, _observe(content), TEXT).passed is expected


def test_a_failing_assertion_carries_a_detail_and_a_passing_one_does_not() -> None:
    """The detail is what the reviewer reads beside the case. A passing
    assertion with prose attached would be noise on the screen that matters."""
    failed = evaluate(_spec(AssertionType.SUBSTRING, "xyz"), _observe("hello"), TEXT)
    passed = evaluate(_spec(AssertionType.SUBSTRING, "ell"), _observe("hello"), TEXT)

    assert failed.detail
    assert passed.detail is None


def test_json_schema_validates_the_parsed_output_and_a_non_json_output_fails() -> None:
    schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}

    assert evaluate(_spec(AssertionType.JSON_SCHEMA, schema), _observe('{"ok": true}'), TEXT).passed
    assert not evaluate(
        _spec(AssertionType.JSON_SCHEMA, schema), _observe('{"ok": 1}'), TEXT
    ).passed

    # Not JSON at all is a FAIL rather than an error: the prompt was asked for
    # JSON and returned prose, which is evidence about the prompt.
    outcome = evaluate(_spec(AssertionType.JSON_SCHEMA, schema), _observe("hello"), TEXT)
    assert not outcome.passed
    assert outcome.detail == "the output is not JSON"


def test_max_latency_reads_the_measured_latency_and_is_unevaluable_without_one() -> None:
    assert evaluate(_spec(AssertionType.MAX_LATENCY, 500), _observe("x", latency_ms=100), TEXT).passed
    assert not evaluate(
        _spec(AssertionType.MAX_LATENCY, 50), _observe("x", latency_ms=100), TEXT
    ).passed

    with pytest.raises(AssertionUnevaluable):
        evaluate(_spec(AssertionType.MAX_LATENCY, 50), _observe("x"), TEXT)


def test_max_cost_is_unevaluable_because_call_ledger_prices_per_run(caplog) -> None:
    """A KNOWN, RECORDED LIMIT rather than a bug — OQ-145.

    A-005 lists `max_cost` among the assertion types, and call-ledger owns money
    (A-030, ADR-0019). INT-021 answers per RUN — `get_run_totals(run_id)` — and
    there is no per-case read anywhere on that seam; evaluation may not query
    `ledger.call_record` itself, because call-ledger is a sink. So the executor
    has no cost to hand this evaluator at the moment a case is judged.

    The answer is `outcome = error`, LOUDLY, rather than a silent pass: A-057's
    rule is that a failure of the machinery is never evidence about a prompt, and
    a `max_cost` assertion that always passed would be worse than one that
    refuses to answer. `EvalCaseErrorRateHigh` is what makes it visible.
    """
    with pytest.raises(AssertionUnevaluable):
        evaluate(_spec(AssertionType.MAX_COST, "0.01"), _observe("x"), TEXT)

    # It answers normally the moment a cost is supplied, so the limit is the
    # executor's missing input rather than the evaluator.
    assert evaluate(
        _spec(AssertionType.MAX_COST, "0.01"), _observe("x", cost=Decimal("0.005")), TEXT
    ).passed


# --- the structured evaluators ---------------------------------------------


def test_asset_count_counts_a_list_a_single_object_and_a_bare_reference() -> None:
    assert evaluate(_spec(AssertionType.ASSET_COUNT, 2), _observe('[{"a": 1}, {"a": 2}]'), STRUCTURED).passed
    assert evaluate(_spec(AssertionType.ASSET_COUNT, 1), _observe('{"a": 1}'), STRUCTURED).passed
    assert evaluate(
        _spec(AssertionType.ASSET_COUNT, 1), _observe("https://example.test/a.png"), STRUCTURED
    ).passed


def test_asset_type_reads_the_declared_type_and_not_the_bytes() -> None:
    """The limit A-061 states out loud rather than engineering around: a
    deterministic assertion reaches the SHAPE of the response and nothing about
    whether the asset is any good. Whether the image is a good image is shown
    side by side for a human and is never scored."""
    assert evaluate(
        _spec(AssertionType.ASSET_TYPE, "image/png"),
        _observe('{"content_type": "image/png", "url": "https://example.test/a.png"}'),
        STRUCTURED,
    ).passed

    assert not evaluate(
        _spec(AssertionType.ASSET_TYPE, "image/png"),
        _observe('{"content_type": "application/pdf"}'),
        STRUCTURED,
    ).passed


# --- compile-time refusals -------------------------------------------------


def test_an_invalid_regex_is_refused_at_authoring_where_its_author_can_fix_it() -> None:
    """Compiled at suite save time on purpose. The alternative is a pattern that
    is syntactically wrong being discovered on a paid run, inside `worker`,
    against a case the author is no longer looking at."""
    with pytest.raises(AssertionPatternInvalid) as refusal:
        compile_assertions([_spec(AssertionType.REGEX, "(unclosed")], TEXT, ordinal=3)

    assert refusal.value.ordinal == 3
    assert refusal.value.detail


def test_an_invalid_json_schema_is_refused_at_authoring() -> None:
    with pytest.raises(AssertionPatternInvalid):
        compile_assertions(
            [_spec(AssertionType.JSON_SCHEMA, {"type": "not-a-json-schema-type"})],
            TEXT,
            ordinal=1,
        )


def test_an_assertion_outside_the_declared_modality_is_refused_at_authoring() -> None:
    """A-061 enforced where the author can act on it, rather than as twenty
    identical case errors on a run they then have to interpret."""
    with pytest.raises(AssertionPatternInvalid) as refusal:
        compile_assertions([_spec(AssertionType.SUBSTRING, "x")], STRUCTURED, ordinal=1)

    assert "structured" in refusal.value.detail


@pytest.mark.parametrize(
    "assertion_type",
    [AssertionType.MAX_LENGTH, AssertionType.MAX_LATENCY, AssertionType.ASSET_COUNT],
)
def test_a_bound_that_is_not_a_non_negative_integer_is_refused(assertion_type) -> None:
    modality = STRUCTURED if assertion_type is AssertionType.ASSET_COUNT else TEXT

    for bad in ("ten", -1, True, None):
        with pytest.raises(AssertionPatternInvalid):
            compile_assertions([_spec(assertion_type, bad)], modality, ordinal=1)


def test_a_valid_suite_compiles_and_round_trips_through_the_stored_json() -> None:
    specs = compile_assertions(
        [_spec(AssertionType.REGEX, r"\bhello\b"), _spec(AssertionType.MAX_LENGTH, 100)],
        TEXT,
        ordinal=1,
    )

    stored = [spec.as_json() for spec in specs]
    assert parse_assertions(stored) == specs


# --- the modality check ----------------------------------------------------


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("hello there", "text"),
        ('{"a": 1}', "structured"),
        ("[1, 2, 3]", "structured"),
        ("https://example.test/a.png", "asset_reference"),
        ("data:image/png;base64,AAA", "asset_reference"),
        ("{not json at all", "text"),
        ("", "empty"),
        (None, "empty"),
    ],
)
def test_the_returned_shape_is_read_from_the_content(content, expected) -> None:
    assert returned_shape(content) == expected


def test_every_asset_scheme_is_recognised() -> None:
    for scheme in ASSET_SCHEMES:
        assert returned_shape(f"{scheme}somewhere/a.png") == "asset_reference"


def test_a_text_suite_against_a_structured_target_names_both_shapes() -> None:
    """The most expensive kind of wrong signal this module can produce, which is
    why the run is REFUSED rather than reported: every text assertion would fail
    at once and the reviewer would read a configuration mistake as a
    catastrophic regression."""
    with pytest.raises(ModalityMismatch) as mismatch:
        check_modality(TEXT, '{"asset": "https://example.test/a.png"}')

    assert mismatch.value.declared is TEXT
    assert mismatch.value.returned == "structured"
    assert "text" in str(mismatch.value)
    assert "structured" in str(mismatch.value)


def test_a_structured_suite_against_prose_is_a_mismatch_in_the_other_direction() -> None:
    with pytest.raises(ModalityMismatch):
        check_modality(STRUCTURED, "here is some prose")


def test_a_matching_modality_and_an_empty_answer_both_pass_the_check() -> None:
    """An empty response is not a modality mismatch. It is an ordinary case
    outcome, judged by whatever assertions the suite carries."""
    check_modality(TEXT, "prose")
    check_modality(STRUCTURED, '{"a": 1}')
    check_modality(STRUCTURED, "https://example.test/a.png")
    check_modality(TEXT, "")
    check_modality(TEXT, None)


# --- T-009: the regex blast radius -----------------------------------------


def test_a_catastrophically_backtracking_pattern_aborts_inside_its_budget() -> None:
    """T-009, HIGH. **A regex assertion is USER-AUTHORED CODE running in
    `worker`**, and that container also runs call-ledger's drain, call-ledger's
    retention job and provider-access's batch dispatch (ADR-0049).

    Stdlib `re` has no timeout and holds the GIL in C without yielding, so one
    prompt owner's typo would stall three other modules — from a field that is
    user-authored BY DESIGN (A-005). The `regex` module checks its deadline
    periodically and raises instead of running to completion.

    A timeout is `outcome = error`, never `fail` (A-057): the same rule that
    keeps a dispatch failure from reading as evidence about a prompt, applied to
    a failure of the assertion machinery instead of the provider.
    """
    started = time.perf_counter()

    with pytest.raises(AssertionTimeout) as timeout:
        evaluate(
            _spec(AssertionType.REGEX, r"(a+)+$"),
            _observe("a" * 4000 + "b"),
            TEXT,
        )

    elapsed = time.perf_counter() - started

    assert timeout.value.error_code == "assertion_timeout"
    # Generous against the 1.0 s budget: the assertion is that the match ABORTS
    # rather than that it aborts to the millisecond, and a loaded CI box is not
    # a reason for this to be flaky. Without the timeout this pattern does not
    # finish in any wall clock anybody waits for.
    assert elapsed < 10 * REGEX_TIMEOUT_SECONDS, elapsed


def test_a_long_input_is_bounded_before_the_match_as_a_second_line_of_defence() -> None:
    """Belt beside the braces. The timeout is the control; the length bound is
    what keeps an ordinary large output from spending the whole budget."""
    from prope.evaluation.domain import MAX_ASSERTION_INPUT_CHARACTERS

    oversize = "x" * (MAX_ASSERTION_INPUT_CHARACTERS + 5000) + "needle"

    outcome = evaluate(_spec(AssertionType.REGEX, "needle"), _observe(oversize), TEXT)

    # The needle is past the bound, so the match legitimately fails — which is
    # the observable consequence of the truncation and the reason it is a
    # SECOND line of defence rather than the first.
    assert not outcome.passed


def test_evaluate_all_returns_one_outcome_per_assertion_in_order() -> None:
    specs = (
        _spec(AssertionType.SUBSTRING, "hello"),
        _spec(AssertionType.MAX_LENGTH, 3),
        _spec(AssertionType.EXACT, "hello world"),
    )

    outcomes = evaluate_all(specs, _observe("hello world"), TEXT)

    assert [entry.type for entry in outcomes] == [spec.type for spec in specs]
    assert [entry.passed for entry in outcomes] == [True, False, True]

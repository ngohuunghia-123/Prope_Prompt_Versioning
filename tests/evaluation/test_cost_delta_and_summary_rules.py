"""The arithmetic behind the one number a reviewer is asked to act on, and the
five ways it is withheld instead of being shown wrong.

**A delta over a partly unpriced or partly errored run is not a delta.** A-057
withholds it on any dispatch error and A-101 withholds it on any unpriced or
unknown-usage row, and both exist for the same reason: a smaller number that
looks like a cheaper revision is worse than an honest blank. Every branch below
returns `None` plus a stated reason, never a number.

**`requires_acknowledgement` is computed HERE and nowhere else** (A-058,
ADR-0005). Release-control ENFORCES it and never recomputes it, so the two
carve-outs are applied once in this file: an error is not a fail (A-057), and an
empty suite is not a pass (A-059).
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from prope.evaluation.comparison import (
    RunMeasurement,
    compare_cases,
    cost_delta,
    is_cost_warning,
    measure,
    requires_acknowledgement,
    roll_up,
)
from prope.evaluation.domain import (
    COST_WARNING_BLOCKS,
    COST_WARNING_THRESHOLD,
    CaseOutcome,
    CaseResultRow,
    CaseRow,
    CostDelta,
    RunRole,
    RunRow,
    RunStatus,
    SuiteSummary,
    SuiteVersionMismatch,
    WithheldReason,
)

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _measurement(
    *,
    run_id: str = "evr_candidate",
    suite_id: str = "evs_safety_4",
    status: RunStatus = RunStatus.COMPLETED,
    error_count: int = 0,
    input_tokens: int | None = 1000,
    output_tokens: int | None = 500,
    cost: Decimal | None = Decimal("1.00"),
    currency: str | None = "USD",
    priced: bool = True,
) -> RunMeasurement:
    return RunMeasurement(
        run_id=run_id,
        suite_id=suite_id,
        status=status,
        error_count=error_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        currency=currency,
        priced=priced,
    )


def _summary(
    *,
    name: str = "safety",
    fail_count: int = 0,
    error_count: int = 0,
    delta: CostDelta | None = None,
    withheld: WithheldReason | None = None,
    warning: bool = False,
) -> SuiteSummary:
    return SuiteSummary(
        suite_id=f"evs_{name}",
        suite_name=name,
        suite_version=4,
        run_id=f"evr_{name}",
        status=RunStatus.COMPLETED,
        pass_count=20 - fail_count - error_count,
        fail_count=fail_count,
        error_count=error_count,
        case_count=20,
        baseline_run_id="evr_baseline",
        baseline_ran_at=NOW,
        baseline_reused=True,
        cost_delta=delta,
        withheld_reason=withheld,
        cost_warning=warning,
    )


# --- the happy delta -------------------------------------------------------


def test_a_clean_pair_yields_a_token_and_money_delta_and_a_ratio() -> None:
    delta, withheld = cost_delta(
        _measurement(input_tokens=1200, output_tokens=600, cost=Decimal("1.50")),
        _measurement(run_id="evr_baseline", input_tokens=1000, output_tokens=500, cost=Decimal("1.00")),
    )

    assert withheld is None
    assert delta == CostDelta(
        input_tokens=200,
        output_tokens=100,
        cost=Decimal("0.50"),
        currency="USD",
        ratio=Decimal("1.5"),
    )


def test_a_cheaper_candidate_yields_negative_deltas_and_a_ratio_below_one() -> None:
    """The direction is candidate minus baseline, so cheaper reads negative.
    Asserted because a sign flip here would render every improvement as a
    regression on the one screen that decides a release."""
    delta, _ = cost_delta(
        _measurement(input_tokens=800, output_tokens=400, cost=Decimal("0.80")),
        _measurement(run_id="evr_baseline"),
    )

    assert delta.input_tokens == -200
    assert delta.output_tokens == -100
    assert delta.cost == Decimal("-0.20")
    assert delta.ratio < 1


# --- the five withholdings -------------------------------------------------


def test_no_baseline_withholds_rather_than_reporting_an_absolute_as_a_delta() -> None:
    """A-060: with no released revision there is no baseline, the run is
    reported absolutely, and the cost delta is OMITTED. Zero would be a lie in
    the most convincing possible shape — a delta of nothing looks like parity."""
    delta, withheld = cost_delta(_measurement(), None)

    assert delta is None
    assert withheld is WithheldReason.NO_BASELINE


@pytest.mark.parametrize("side", ["candidate", "baseline"])
def test_any_dispatch_error_on_either_side_withholds_the_delta(side) -> None:
    """A-057. Three of twenty cases that could not be run means the run measured
    seventeen, and seventeen cases' cost is not this revision's cost."""
    candidate = _measurement(error_count=3 if side == "candidate" else 0)
    baseline = _measurement(run_id="evr_baseline", error_count=3 if side == "baseline" else 0)

    delta, withheld = cost_delta(candidate, baseline)

    assert delta is None
    assert withheld is WithheldReason.HAS_ERRORS


def test_an_unpriced_run_withholds_the_delta_rather_than_treating_null_as_zero() -> None:
    """A-101, ADR-0019. A call with no price row records a NULL cost rather than
    zero, and `get_run_totals`' two counts exist to say so — a delta computed
    over those rows would be confidently wrong."""
    delta, withheld = cost_delta(
        _measurement(priced=False, cost=None), _measurement(run_id="evr_baseline")
    )

    assert delta is None
    assert withheld is WithheldReason.UNPRICED


def test_a_run_with_no_usage_object_withholds_the_delta() -> None:
    """A-030 makes a usage object the precondition for supporting a provider at
    all. Absent counts are NULL on both columns together and never a zero."""
    delta, withheld = cost_delta(
        _measurement(input_tokens=None, output_tokens=None), _measurement(run_id="evr_baseline")
    )

    assert delta is None
    assert withheld is WithheldReason.UNKNOWN_USAGE


def test_two_currencies_withhold_rather_than_summing_a_number_with_no_unit() -> None:
    """A-107 forbids conversion, and an exchange rate would be a second
    effective-dated table nobody has agreed to maintain."""
    delta, withheld = cost_delta(
        _measurement(currency="USD"), _measurement(run_id="evr_baseline", currency="VND")
    )

    assert delta is None
    assert withheld is WithheldReason.MIXED_CURRENCY


def test_an_unfinished_run_on_either_side_withholds_the_delta() -> None:
    delta, withheld = cost_delta(
        _measurement(status=RunStatus.INTERRUPTED), _measurement(run_id="evr_baseline")
    )

    assert delta is None
    assert withheld is WithheldReason.RUN_INCOMPLETE


def test_pairing_two_different_suite_versions_raises_and_names_both() -> None:
    """The yardstick pin. Without it two revisions get measured with two
    different rulers and the pass/fail comparison is meaningless while looking
    authoritative — so this RAISES rather than withholding, because a
    cross-version comparison is a caller bug and not a missing number."""
    with pytest.raises(SuiteVersionMismatch) as mismatch:
        cost_delta(_measurement(suite_id="evs_safety_5"), _measurement(suite_id="evs_safety_4"))

    assert "evs_safety_5" in str(mismatch.value)
    assert "evs_safety_4" in str(mismatch.value)


# --- the warning, and the fact that it never blocks -------------------------


def test_the_warning_threshold_is_twenty_percent_and_fires_at_the_boundary() -> None:
    """OQ-009, resolved by the user: warn at >= +20%, never block. The `>=` is
    the decision rather than a convention — at exactly the threshold the
    candidate IS twenty percent more expensive."""
    assert COST_WARNING_THRESHOLD == Decimal("0.20")

    at_threshold = CostDelta(0, 0, Decimal("0.20"), "USD", ratio=Decimal("1.20"))
    just_under = CostDelta(0, 0, Decimal("0.19"), "USD", ratio=Decimal("1.19"))

    assert is_cost_warning(at_threshold)
    assert not is_cost_warning(just_under)


def test_a_withheld_delta_raises_no_warning_because_there_is_nothing_to_compare() -> None:
    assert not is_cost_warning(None)
    assert not is_cost_warning(CostDelta(0, 0, None, None, ratio=None))


def test_the_block_flag_is_configuration_and_defaults_to_off() -> None:
    """FR-08 keeps both the threshold and the block flag configurable; OQ-009
    fixes the DEFAULTS at 20% and off. Nothing about cost can refuse a release —
    the product's one hard gate stays singular, that the revision is not
    Approved, and that refusal lives in a database constraint."""
    assert COST_WARNING_BLOCKS is False


# --- the rollup ------------------------------------------------------------


def test_the_rollup_sums_the_per_suite_deltas_when_every_one_is_valid() -> None:
    delta, withheld, warning = roll_up(
        [
            _summary(name="safety", delta=CostDelta(100, 50, Decimal("0.10"), "USD", Decimal("1.1"))),
            _summary(name="accuracy", delta=CostDelta(200, 80, Decimal("0.20"), "USD", Decimal("1.0"))),
        ]
    )

    assert withheld is None
    assert not warning
    assert delta.input_tokens == 300
    assert delta.output_tokens == 130
    assert delta.cost == Decimal("0.30")
    assert delta.currency == "USD"


def test_the_rollup_is_withheld_when_any_one_suite_withheld_its_own() -> None:
    """A-062, and the half that is easy to get wrong: **the valid per-suite
    deltas are still returned.** Withholding the total is not the same as
    withholding the evidence."""
    summaries = [
        _summary(name="safety", delta=CostDelta(100, 50, Decimal("0.10"), "USD", Decimal("1.1"))),
        _summary(name="accuracy", error_count=2, withheld=WithheldReason.HAS_ERRORS),
    ]

    delta, withheld, _ = roll_up(summaries)

    assert delta is None
    assert withheld is WithheldReason.HAS_ERRORS
    assert summaries[0].cost_delta is not None


def test_the_rollup_warns_when_any_one_suite_warns() -> None:
    _, _, warning = roll_up(
        [_summary(name="safety"), _summary(name="accuracy", warning=True)]
    )

    assert warning


def test_the_rollup_has_no_ratio_because_a_ratio_of_sums_is_not_a_ratio() -> None:
    """Deliberate. The per-suite ratio is what
    `prope_evaluation_cost_delta_ratio` observes and what the threshold reads;
    a rolled-up ratio would weight a cheap suite equally with an expensive one
    and read as a single headline number nobody could act on."""
    delta, _, _ = roll_up(
        [_summary(name="safety", delta=CostDelta(1, 1, Decimal("0.10"), "USD", Decimal("3.0")))]
    )

    assert delta.ratio is None


# --- requires_acknowledgement, and its two carve-outs ----------------------


def test_any_failing_case_in_any_suite_requires_an_acknowledgement() -> None:
    """AC-8's last clause. ANY, not all: a reviewer approving over one failing
    safety case has to say why, whatever the other two suites did."""
    assert requires_acknowledgement(
        [_summary(name="safety"), _summary(name="accuracy", fail_count=1), _summary(name="format")]
    )


def test_an_error_is_not_a_fail_and_does_not_require_an_acknowledgement() -> None:
    """A-057's carve-out, applied ONCE here so release-control never restates
    it. Three cases that could not be dispatched are not three failures — an
    unreachable provider is not evidence about a prompt, and asking for a
    written reason about it would train reviewers to type one word."""
    assert not requires_acknowledgement([_summary(name="safety", error_count=3)])


def test_an_empty_suite_is_not_a_pass_and_still_requires_nothing() -> None:
    """A-059's carve-out. An empty suite renders as *'no eval suite'* rather
    than as a green tick — but it has no failing case either, so it does not
    force an acknowledgement. The screen says there is no evidence; it does not
    manufacture a decision from the absence of one."""
    empty = SuiteSummary(
        suite_id="evs_empty",
        suite_name="safety",
        suite_version=1,
        run_id="evr_empty",
        status=RunStatus.COMPLETED,
        pass_count=0,
        fail_count=0,
        error_count=0,
        case_count=0,
        baseline_run_id=None,
        baseline_ran_at=None,
        baseline_reused=False,
        cost_delta=None,
        withheld_reason=WithheldReason.NO_BASELINE,
        cost_warning=False,
    )

    assert not requires_acknowledgement([empty])
    assert empty.pass_count == 0


def test_no_suites_at_all_requires_no_acknowledgement() -> None:
    assert not requires_acknowledgement([])


# --- per-case comparison ---------------------------------------------------


def _case(case_id: str, ordinal: int) -> CaseRow:
    return CaseRow(
        id=case_id,
        workspace_id="wsp_1",
        suite_id="evs_safety_4",
        ordinal=ordinal,
        name=f"case {ordinal}",
        input_messages=(),
        input_variables={},
        assertions=(),
        created_at=NOW,
    )


def _result(case_id: str, outcome: CaseOutcome) -> CaseResultRow:
    return CaseResultRow(
        id=f"evcr_{case_id}",
        workspace_id="wsp_1",
        run_id="evr_x",
        case_id=case_id,
        outcome=outcome,
        assertion_results=(),
        output_content=None,
        latency_ms=10,
        input_tokens=1,
        output_tokens=1,
        error_code="upstream_timeout" if outcome is CaseOutcome.ERROR else None,
        error_detail=None,
        attempt_count=1,
        created_at=NOW,
    )


def test_a_case_whose_outcome_moved_between_the_two_runs_is_labelled_changed() -> None:
    """Flips are SURFACED, not smoothed. At a non-zero temperature the same
    revision can answer differently twice, and the answer to that is to show
    both outputs side by side — never an automatic re-run that turns a fail into
    a pass."""
    cases = [_case("evc_1", 1), _case("evc_2", 2)]

    comparisons = compare_cases(
        cases,
        [_result("evc_1", CaseOutcome.PASS), _result("evc_2", CaseOutcome.FAIL)],
        [_result("evc_1", CaseOutcome.PASS), _result("evc_2", CaseOutcome.PASS)],
    )

    assert [entry.changed for entry in comparisons] == [False, True]
    assert comparisons[1].baseline_outcome is CaseOutcome.PASS
    assert comparisons[1].candidate_outcome is CaseOutcome.FAIL


def test_a_case_with_no_baseline_result_is_not_labelled_changed() -> None:
    """Nothing to compare against is not a change. Labelling it one would put a
    'changed' badge on every case of the first run a prompt ever has."""
    comparisons = compare_cases(
        [_case("evc_1", 1)], [_result("evc_1", CaseOutcome.FAIL)], []
    )

    assert comparisons[0].baseline_outcome is None
    assert comparisons[0].changed is False


def test_a_case_the_candidate_never_reached_is_absent_rather_than_invented() -> None:
    """An interrupted run has partial results, and the comparison shows what was
    measured. A row with a blank candidate column would read as a result."""
    comparisons = compare_cases(
        [_case("evc_1", 1), _case("evc_2", 2)],
        [_result("evc_1", CaseOutcome.PASS)],
        [_result("evc_1", CaseOutcome.PASS), _result("evc_2", CaseOutcome.PASS)],
    )

    assert [entry.case_id for entry in comparisons] == ["evc_1"]


# --- measure() -------------------------------------------------------------


def test_measure_reads_priced_from_the_timestamp_and_not_from_the_amount() -> None:
    """`priced_at` is the fact and `cost_amount` is the figure. A run priced at
    a genuine zero cannot exist — `ck_call_record_cost_is_never_zero` — but
    reading the amount would still conflate 'not priced yet' with a number."""
    run = RunRow(
        id="evr_1",
        workspace_id="wsp_1",
        prompt_id="prm_1",
        version_id="rev_1",
        suite_id="evs_1",
        role=RunRole.CANDIDATE,
        status=RunStatus.COMPLETED,
        refused_reason=None,
        started_at=NOW,
        finished_at=NOW,
        pass_count=18,
        fail_count=2,
        error_count=0,
        input_tokens=100,
        output_tokens=50,
        cost_amount=None,
        cost_currency=None,
        priced_at=None,
        started_by="usr_1",
    )

    measured = measure(run)

    assert measured.priced is False
    assert measured.cost is None
    assert measured.error_count == 0

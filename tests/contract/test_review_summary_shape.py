"""INT-017 — the one internal read release-control pulls, and its whole surface.

``release-control`` does not exist yet. That is the reason this file exists
rather than a reason to defer it: wave 5 will be written *from* this shape, and a
shape that is wrong is cheapest to find now. The same argument
``tests/contract/test_registry_seams.py`` makes for the six seams this module was
written against.

Three properties, and the second and third are the ones a caller cannot recover
from if they are wrong:

* **the field names**, because release-control renders them and A-042 says it
  renders these numbers rather than recomputing them;
* **``requires_acknowledgement`` is computed here, once** (A-058). Release-control
  enforces it and never recomputes it, so a caller that had to re-derive the rule
  would be a second copy of A-057's and A-059's carve-outs, in a module that owns
  neither;
* **the rollup withholds whenever any suite withheld**, while the per-suite
  deltas that ARE valid are still returned. A caller that summed the rows itself
  would publish a total this module refused to publish.
"""

from dataclasses import fields, is_dataclass
from decimal import Decimal

import pytest
from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.evaluation import seams
from prope.evaluation.domain import (
    CostDelta,
    ReviewSummary,
    RunStatus,
    SuiteSummary,
    WithheldReason,
)
from tests.evaluation import (
    PROMPT_ID,
    VERSION_ID,
    WORKSPACE_A,
    day,
    seed_bound_revision,
    seed_case,
    seed_owner,
    seed_run,
    seed_suite,
)
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_evaluation_int017_00001"

RELEASED_VERSION = "rev_01J000000000000000RELEAS"

SAFETY = "evs_01J00000000000000SAFETY1"

ACCURACY = "evs_01J0000000000000ACCURA1"

CANDIDATE_SAFETY = "evr_01J0000000000000CANDSAF1"

CANDIDATE_ACCURACY = "evr_01J0000000000000CANDACC1"

BASELINE_SAFETY = "evr_01J0000000000000BASESAF1"

BASELINE_ACCURACY = "evr_01J0000000000000BASEACC1"

PRICED = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cost_currency": "USD",
    "priced_at": day(2),
    "finished_at": day(2),
}


async def _two_suites_measured_against_a_released_revision(migrate_engine) -> None:  # noqa: ANN001
    """Two suites, both measured on both revisions, both fully priced.

    Seeded as rows rather than executed, because what is under test is the
    projection and not the executor: a test that had to run twenty dispatches to
    assert a field name would fail for reasons that have nothing to do with
    INT-017.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(migrate_engine, RELEASED_VERSION, revision_number=1)
    await seed_bound_revision(migrate_engine, VERSION_ID, revision_number=2)
    await approve(migrate_engine, RELEASED_VERSION)
    await release(migrate_engine, PROMPT_ID, RELEASED_VERSION)

    await seed_suite(migrate_engine, SAFETY, name="safety", case_count=2)
    await seed_case(migrate_engine, "evc_01J00000000000000SAFE001", suite_id=SAFETY, ordinal=1)
    await seed_case(migrate_engine, "evc_01J00000000000000SAFE002", suite_id=SAFETY, ordinal=2)

    await seed_suite(migrate_engine, ACCURACY, name="accuracy", case_count=2)
    await seed_case(migrate_engine, "evc_01J00000000000000ACCU001", suite_id=ACCURACY, ordinal=1)
    await seed_case(migrate_engine, "evc_01J00000000000000ACCU002", suite_id=ACCURACY, ordinal=2)

    await seed_run(
        migrate_engine,
        BASELINE_SAFETY,
        suite_id=SAFETY,
        version_id=RELEASED_VERSION,
        role="baseline",
        status="completed",
        pass_count=2,
        cost_amount=Decimal("1.00"),
        **PRICED,
    )
    await seed_run(
        migrate_engine,
        BASELINE_ACCURACY,
        suite_id=ACCURACY,
        version_id=RELEASED_VERSION,
        role="baseline",
        status="completed",
        pass_count=2,
        cost_amount=Decimal("2.00"),
        **PRICED,
    )
    await seed_run(
        migrate_engine,
        CANDIDATE_SAFETY,
        suite_id=SAFETY,
        version_id=VERSION_ID,
        status="completed",
        pass_count=2,
        cost_amount=Decimal("1.10"),
        **PRICED,
    )
    await seed_run(
        migrate_engine,
        CANDIDATE_ACCURACY,
        suite_id=ACCURACY,
        version_id=VERSION_ID,
        status="completed",
        pass_count=2,
        cost_amount=Decimal("2.20"),
        **PRICED,
    )


def test_the_seam_module_exposes_int017_and_its_types_and_nothing_else() -> None:
    """The whole public surface, asserted as a set.

    A seam that grew a second function would let release-control depend on
    something this module never registered as a contract — the failure ADR-0023's
    seam-module convention exists to make visible in a diff.
    """
    assert set(seams.__all__) == {
        "CostDelta",
        "ReviewSummary",
        "RunStatus",
        "SuiteSummary",
        "WithheldReason",
        "get_review_summary",
    }
    assert seams.get_review_summary is not None


def test_the_returned_types_are_frozen_dataclasses_with_the_declared_fields() -> None:
    """INT-017's field names, read from the types rather than from a response.

    Frozen because release-control renders these and must not be able to adjust
    them on the way past; asserted by name because a rename is a breaking change
    to a contract and should read as one.
    """
    assert is_dataclass(ReviewSummary)
    assert is_dataclass(SuiteSummary)
    assert is_dataclass(CostDelta)

    assert {field.name for field in fields(ReviewSummary)} == {
        "prompt_id",
        "version_id",
        "suites",
        "total_cost_delta",
        "withheld_reason",
        "cost_warning",
        "requires_acknowledgement",
    }

    assert {field.name for field in fields(SuiteSummary)} == {
        "suite_id",
        "suite_name",
        "suite_version",
        "run_id",
        "status",
        "pass_count",
        "fail_count",
        "error_count",
        "case_count",
        "baseline_run_id",
        "baseline_ran_at",
        "baseline_reused",
        "cost_delta",
        "withheld_reason",
        "cost_warning",
    }

    assert {field.name for field in fields(CostDelta)} == {
        "input_tokens",
        "output_tokens",
        "cost",
        "currency",
        "ratio",
    }

    with pytest.raises(Exception):
        CostDelta(
            input_tokens=0, output_tokens=0, cost=None, currency=None, ratio=None
        ).input_tokens = 1


async def test_a_fully_priced_summary_carries_per_suite_rows_and_a_rollup(
    app_sessionmaker, migrate_engine
) -> None:
    """The happy path, and the arithmetic release-control will render.

    The rollup's cost is the SUM of the per-suite deltas and its ``ratio`` is
    ``None`` — a ratio of sums across suites of different sizes would be a number
    with no meaning, and publishing one would invite it to be compared against
    the per-suite threshold.
    """
    await _two_suites_measured_against_a_released_revision(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        summary = await seams.get_review_summary(db, PROMPT_ID, VERSION_ID)

    assert isinstance(summary, ReviewSummary)
    assert summary.prompt_id == PROMPT_ID
    assert summary.version_id == VERSION_ID

    by_name = {row.suite_name: row for row in summary.suites}
    assert set(by_name) == {"safety", "accuracy"}

    assert by_name["safety"].status is RunStatus.COMPLETED
    assert by_name["safety"].run_id == CANDIDATE_SAFETY
    assert by_name["safety"].baseline_run_id == BASELINE_SAFETY
    assert by_name["safety"].baseline_reused is True
    assert by_name["safety"].baseline_ran_at == day(2)
    assert by_name["safety"].withheld_reason is None
    assert by_name["safety"].cost_delta.cost == Decimal("0.10")
    assert by_name["safety"].cost_delta.currency == "USD"

    assert summary.withheld_reason is None
    assert summary.total_cost_delta is not None
    assert summary.total_cost_delta.cost == Decimal("0.30")
    assert summary.total_cost_delta.currency == "USD"
    assert summary.total_cost_delta.ratio is None
    assert summary.requires_acknowledgement is False


async def test_the_rollup_withholds_when_any_one_suite_withholds(
    app_sessionmaker, migrate_engine
) -> None:
    """The composition rule, and the reason a caller must not sum the rows.

    The accuracy candidate has an error, so its own delta is withheld — and the
    rollup goes with it, because a total over the suites that happened to be
    clean is a smaller number that reads as a cheaper revision. The safety row
    keeps its valid delta, so the reviewer still sees what is known.
    """
    await _two_suites_measured_against_a_released_revision(migrate_engine)

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text("UPDATE evaluation.eval_run SET error_count = 1 WHERE id = :run_id"),
            {"run_id": CANDIDATE_ACCURACY},
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        summary = await seams.get_review_summary(db, PROMPT_ID, VERSION_ID)

    by_name = {row.suite_name: row for row in summary.suites}

    assert by_name["accuracy"].cost_delta is None
    assert by_name["accuracy"].withheld_reason is WithheldReason.HAS_ERRORS

    assert by_name["safety"].cost_delta is not None
    assert by_name["safety"].withheld_reason is None

    assert summary.total_cost_delta is None
    assert summary.withheld_reason is WithheldReason.HAS_ERRORS


async def test_requires_acknowledgement_survives_the_two_carve_outs(
    app_sessionmaker, migrate_engine
) -> None:
    """A-057 and A-059 applied once, here, and asserted as the flag's boundary.

    An ``error`` is not a ``fail``, so a run of nothing but errors does not
    require an acknowledgement — there is nothing to acknowledge, the run did not
    measure anything. One real failing case does.
    """
    await _two_suites_measured_against_a_released_revision(migrate_engine)

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE evaluation.eval_run SET error_count = 2, pass_count = 0 "
                "WHERE id = :run_id"
            ),
            {"run_id": CANDIDATE_ACCURACY},
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        errors_only = await seams.get_review_summary(db, PROMPT_ID, VERSION_ID)

    assert errors_only.requires_acknowledgement is False

    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE evaluation.eval_run SET fail_count = 1, pass_count = 1 "
                "WHERE id = :run_id"
            ),
            {"run_id": CANDIDATE_SAFETY},
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        with_a_failure = await seams.get_review_summary(db, PROMPT_ID, VERSION_ID)

    assert with_a_failure.requires_acknowledgement is True


async def test_a_version_with_no_runs_answers_an_empty_summary_rather_than_raising(
    app_sessionmaker, migrate_engine
) -> None:
    """The absent case, which release-control hits on every un-evaluated revision.

    An empty summary with ``no_baseline`` withheld is a fact about the revision;
    an exception would make "nobody has run the suites yet" an error condition
    the review screen had to catch on its main path.
    """
    await _two_suites_measured_against_a_released_revision(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        summary = await seams.get_review_summary(db, PROMPT_ID, RELEASED_VERSION)

    assert summary.suites == ()
    assert summary.total_cost_delta is None
    assert summary.withheld_reason is WithheldReason.NO_BASELINE
    assert summary.requires_acknowledgement is False

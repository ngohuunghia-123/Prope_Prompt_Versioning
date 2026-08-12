"""INT-009 through INT-014 — the six seams three later modules are written against.

None of these modules exists yet. That is the reason this file exists rather than
a reason to defer it: gateway, evaluation and release-control will be written
*from* these shapes, and a shape that is wrong is cheapest to find now.

**The failure semantics are the contract, as much as the signatures are**, and
they are deliberately not uniform. INT-009 answers a typed MISS rather than
raising, because a model name with nothing released is an ordinary outcome on the
gateway's hot path. INT-012 raises on an illegal transition, INT-013 raises a
CONFLICT on the compare-and-set, and INT-014 raises if nothing is released —
three separate seams precisely because a caller must branch on which one it hit.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.prompt_registry.domain import (
    IllegalTransition,
    ModelName,
    NothingReleased,
    ReleasedPointerConflict,
    ResolveMiss,
    RevisionStatus,
)
from prope.prompt_registry.seams import (
    clear_released_revision,
    get_diff,
    get_released_revision,
    get_revision,
    list_released,
    resolve,
    set_released_revision,
    set_revision_status,
)
from tests.prompt_registry import (
    PROMPT_ID,
    VERSION_ID,
    approve,
    release,
    seed_prompt,
    seed_revision,
)
from tests.unit import WORKSPACE_A

MODEL = ModelName(namespace="support", name="refund-classifier")

SECOND_VERSION = "rev_01J000000000000000000REV2"

RELEASE_ID = "rel_01J0000000000000000000001"

DECISION_ID = "dec_01J0000000000000000000001"

READ_POINTER = text("SELECT released_version_id FROM registry.prompt_property WHERE id = :id")

READ_STATUS = text("SELECT status FROM registry.revision WHERE version_id = :version_id")


def _miss_count(reason: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "prope_registry_resolve_miss_total", {"reason": reason}
        )
        or 0.0
    )


async def _released_prompt(migrate_engine) -> None:  # noqa: ANN001
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, body="the released body")
    await approve(migrate_engine)
    await release(migrate_engine)


async def test_resolve_returns_the_whole_binding(migrate_engine, app_sessionmaker) -> None:
    """INT-009's hit. Everything the gateway needs to make one call, and no more."""
    await seed_prompt(migrate_engine)
    await seed_revision(
        migrate_engine,
        body="the released body",
        provider_config_id=None,
        parameters='{"temperature": 0.2}',
        fallback_answer="We could not answer that.",
    )
    await approve(migrate_engine)
    await release(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        binding = await resolve(db, WORKSPACE_A, MODEL)

    assert not isinstance(binding, ResolveMiss)
    assert binding.version_id == VERSION_ID
    assert binding.revision_number == 1
    assert binding.body == "the released body"
    assert binding.parameters == {"temperature": 0.2}
    assert binding.fallback_answer == "We could not answer that."
    assert binding.prompt_id == PROMPT_ID


async def test_the_two_misses_are_distinguishable_to_the_metric(
    migrate_engine, app_sessionmaker
) -> None:
    """ADR-0009, and the only place a withdrawal is visible as a withdrawal.

    An unknown name and a known name with nothing released are the SAME 404 to
    the caller — a consumer key that could tell them apart could enumerate the
    registry (A-081, A-116) — and two different lines here. Without the label a
    withdrawal looks exactly like a rise in typos.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)

    unknown_before = _miss_count("unknown_model")
    no_release_before = _miss_count("no_release")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        nothing_released = await resolve(db, WORKSPACE_A, MODEL)
        never_existed = await resolve(
            db, WORKSPACE_A, ModelName(namespace="nobody", name="nothing")
        )

    assert nothing_released is ResolveMiss.NO_RELEASE
    assert never_existed is ResolveMiss.UNKNOWN_MODEL

    assert _miss_count("no_release") == no_release_before + 1
    assert _miss_count("unknown_model") == unknown_before + 1


async def test_a_withdrawal_turns_a_hit_into_a_no_release_miss(
    migrate_engine, app_sessionmaker
) -> None:
    """The sequence ADR-0009 is about, end to end through INT-014."""
    await _released_prompt(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert not isinstance(await resolve(db, WORKSPACE_A, MODEL), ResolveMiss)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await clear_released_revision(db, prompt_id=PROMPT_ID, release_id=RELEASE_ID)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await resolve(db, WORKSPACE_A, MODEL) is ResolveMiss.NO_RELEASE


async def test_a_pin_resolves_a_specific_revision(migrate_engine, app_sessionmaker) -> None:
    """Both pin forms — ``@<n>`` and ``@<version_id>`` — against one statement."""
    await _released_prompt(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body="the second body",
        status="Approved",
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        by_number = await resolve(db, WORKSPACE_A, MODEL, pin="2")
        by_id = await resolve(db, WORKSPACE_A, MODEL, pin=SECOND_VERSION)

    assert by_number.version_id == SECOND_VERSION
    assert by_id.body == "the second body"


async def test_a_pin_at_an_unapproved_revision_is_refused(
    migrate_engine, app_sessionmaker
) -> None:
    """INT-009: *a pin whose revision is not Approved is refused*.

    BR-03's constraint guards the released POINTER, and a pin does not go through
    it — so the refusal has to be here. It renders as a ``no_release`` miss
    rather than as a third reason, because the caller must not be able to tell
    *that revision exists but you may not have it* from *nothing is released*.
    """
    await _released_prompt(migrate_engine)
    await seed_revision(
        migrate_engine, version_id=SECOND_VERSION, revision_number=2, status="Draft"
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await resolve(db, WORKSPACE_A, MODEL, pin="2") is ResolveMiss.NO_RELEASE


async def test_list_released_returns_only_prompts_with_a_current_release(
    migrate_engine, app_sessionmaker
) -> None:
    """INT-010, backing ``GET /v1/models``. Deliberately not the management list."""
    await _released_prompt(migrate_engine)
    await seed_prompt(
        migrate_engine,
        prompt_id="prm_01J0000000000000000DRAFT",
        namespace="support",
        name="unreleased",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_01J0000000000000000DRAFT",
        prompt_id="prm_01J0000000000000000DRAFT",
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        listing = await list_released(db, WORKSPACE_A)

    assert [row.model_name for row in listing] == ["support/refund-classifier"]
    assert listing[0].version_id == VERSION_ID
    assert listing[0].revision_number == 1


async def test_the_read_interface_answers_both_shapes(
    migrate_engine, app_sessionmaker
) -> None:
    """INT-011's ``get_revision`` and ``get_released_revision``."""
    await _released_prompt(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        one = await get_revision(db, VERSION_ID)
        released = await get_released_revision(db, PROMPT_ID)
        missing = await get_revision(db, "rev_01J00000000000000MISSING")

    assert one.change_summary == "first draft"
    assert one.status is RevisionStatus.APPROVED
    assert released.version_id == VERSION_ID
    assert missing is None


async def test_get_diff_returns_both_halves(migrate_engine, app_sessionmaker) -> None:
    """INT-011's third read. A line diff AND a field comparison, in one value."""
    await _released_prompt(migrate_engine)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body="the released body\nplus a line",
        fallback_answer="We could not answer that.",
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        before = await get_revision(db, VERSION_ID)
        after = await get_revision(db, SECOND_VERSION)

    result = get_diff(before, after)

    assert [line.op.value for line in result.lines] == ["equal", "added"]
    changed = {change.field: change for change in result.fields if change.changed}
    assert set(changed) == {"fallback_answer"}
    assert changed["fallback_answer"].after == "We could not answer that."
    assert changed["fallback_answer"].before is None


async def test_set_revision_status_walks_the_state_machine(
    migrate_engine, app_sessionmaker
) -> None:
    """INT-012, and the machine lives here so release-control writes no table it
    does not own (ADR-0008)."""
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await set_revision_status(
            db, version_id=VERSION_ID, status=RevisionStatus.IN_REVIEW, decision_id=DECISION_ID
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await set_revision_status(
            db, version_id=VERSION_ID, status=RevisionStatus.APPROVED, decision_id=DECISION_ID
        )

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(READ_STATUS, {"version_id": VERSION_ID}) == "Approved"


@pytest.mark.parametrize(
    "current,target",
    [
        ("Draft", RevisionStatus.APPROVED),
        ("Approved", RevisionStatus.APPROVED),
        ("Approved", RevisionStatus.IN_REVIEW),
    ],
)
async def test_an_illegal_transition_raises(
    migrate_engine, app_sessionmaker, current: str, target: RevisionStatus
) -> None:
    """Including ``Approved -> Approved``, which is what makes INT-012 NOT idempotent.

    Re-issuing a transition that already happened raises rather than silently
    succeeding, so a double-submit is visible instead of absorbed.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, status=current)

    with pytest.raises(IllegalTransition):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await set_revision_status(
                db, version_id=VERSION_ID, status=target, decision_id=DECISION_ID
            )


async def test_an_unknown_version_raises_the_same_way(
    migrate_engine, app_sessionmaker
) -> None:
    """From release-control's side both are one mistake: the decision it recorded
    cannot be applied, and its transaction must abort along with the history
    event claiming it was."""
    with pytest.raises(IllegalTransition):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await set_revision_status(
                db,
                version_id="rev_01J00000000000000MISSING",
                status=RevisionStatus.IN_REVIEW,
                decision_id=DECISION_ID,
            )


async def test_set_released_revision_is_a_compare_and_set(
    migrate_engine, app_sessionmaker
) -> None:
    """INT-013. A first release expects NULL; a stale expectation is a conflict.

    ``IS NOT DISTINCT FROM`` rather than ``=`` is what makes the first case work:
    the expected value is legitimately NULL, and ``NULL = NULL`` is NULL, which
    would make every first release look like a lost race.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)
    await approve(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await set_released_revision(
            db,
            prompt_id=PROMPT_ID,
            version_id=VERSION_ID,
            release_id=RELEASE_ID,
            expected_current_version_id=None,
        )

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(READ_POINTER, {"id": PROMPT_ID}) == VERSION_ID

    await seed_revision(
        migrate_engine, version_id=SECOND_VERSION, revision_number=2, status="Approved"
    )

    with pytest.raises(ReleasedPointerConflict) as conflict:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await set_released_revision(
                db,
                prompt_id=PROMPT_ID,
                version_id=SECOND_VERSION,
                release_id=RELEASE_ID,
                expected_current_version_id=None,
            )

    assert conflict.value.actual == VERSION_ID
    assert conflict.value.expected is None


async def test_withdrawing_nothing_raises(migrate_engine, app_sessionmaker) -> None:
    """INT-014. A withdrawal of nothing is a caller bug, not a no-op.

    Absorbing it would let release-control write a mandatory-reason
    ``release_withdrawn`` event describing an act that did not happen.
    """
    await seed_prompt(migrate_engine)

    with pytest.raises(NothingReleased):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await clear_released_revision(db, prompt_id=PROMPT_ID, release_id=RELEASE_ID)


async def test_the_seams_take_the_callers_session_and_open_none(
    migrate_engine, app_sessionmaker
) -> None:
    """The property that makes *there is no release without a trail* true.

    If ``set_released_revision`` opened its own transaction it would commit a
    pointer whose release record could still roll back. Asserted by rolling the
    caller's transaction back and finding the pointer unmoved — which only holds
    if the write was inside it.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)
    await approve(migrate_engine)

    async with app_sessionmaker() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"),
                {"ws": WORKSPACE_A},
            )
            await set_released_revision(
                session,
                prompt_id=PROMPT_ID,
                version_id=VERSION_ID,
                release_id=RELEASE_ID,
                expected_current_version_id=None,
            )
            await session.rollback()

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(READ_POINTER, {"id": PROMPT_ID}) is None

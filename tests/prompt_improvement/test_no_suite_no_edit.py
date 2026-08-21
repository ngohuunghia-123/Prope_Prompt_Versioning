"""AC-5 / SR-3 — no suite, no edit. Absolutely, for every family and every anomaly.

**This is the rule with no exception clause, and the absence of the clause is the
design.** The eval gate is the only thing standing between a model-influenced
body and a person's four-second approval. A prompt with no suite has nothing to
gate against — so there is no weakened version of the check to fall back on, no
*"propose it and mark it unverified"*, and no confidence threshold that would let
one through. `ck_improvement_proposal_an_edit_is_gated` says the same thing in the
schema: an `edit` row must carry a body, a family AND a gate run, so a proposal
that skipped the gate cannot be written even by a caller that decided to.

**What happens instead is the interesting part.** The remedy degrades to a `case`
proposal — the shipped library datasets that would make a future edit gateable at
all. That is a suggestion a person can act on, and acting on it is what turns the
prompt into one this module can actually help with next month. Proposing nothing
would have been the safe answer and the useless one.

**Parametrised over every family, not over one.** The check lives in `_propose`
before the transform runs, so a single-family test would pass against an
implementation that special-cased the family it happened to use. The families are
reached through `REACHABLE_FAMILIES` rather than listed, so a fourth one added
later arrives here without anybody remembering to add it.
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.evaluation import gate as gate_module
from prope.prompt_improvement import repository
from prope.prompt_improvement import sweep as sweep_module
from prope.prompt_improvement.domain import (
    REACHABLE_FAMILIES,
    Anomaly,
    DetectorId,
    RemedyFamily,
)
from prope.prompt_improvement.triage import Triaged
from prope.prompt_registry.seams import get_revision, list_released_prompts
from tests.evaluation import (
    PROMPT_ID,
    WORKSPACE_A,
    StubDispatcher,
    allow_ceiling,
    completion,
    day,
    seed_bound_revision,
    seed_owner,
    seed_suite,
)
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_improvement_nosuite_0001"

VERSION_ID = "rev_01J0000000000000NOSUITE1"

BODY = (
    "<system>Bạn là trợ lý hỗ trợ khách hàng của ACME.</system>"
    "<instructions>Trả lời câu hỏi {{cau_hoi}} theo đúng chính sách.</instructions>"
)

PROPOSALS = text(
    """
    SELECT remedy_kind, remedy_family, candidate_body, gate_run_id
      FROM improvement.proposal
     WHERE prompt_id = :prompt_id
    """
)

#: One detector per family, taken from the reachability map rather than written
#: out. A family with no detector behind it would fail AC-10's join long before
#: reaching this file, so this is guaranteed to be total.
DETECTOR_FOR_FAMILY: dict[RemedyFamily, DetectorId] = {
    family: detector
    for detector, families in REACHABLE_FAMILIES.items()
    for family in families
}


@pytest.fixture
async def a_released_prompt_with_no_suite(migrate_engine: AsyncEngine) -> None:
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(
        migrate_engine, version_id=VERSION_ID, body=BODY, status="Approved"
    )
    await approve(migrate_engine, VERSION_ID)
    await release(migrate_engine, PROMPT_ID, VERSION_ID)


@pytest.fixture
def a_dispatcher_that_would_pass(monkeypatch: pytest.MonkeyPatch) -> StubDispatcher:
    """A gate that would happily approve, so the refusal cannot be luck.

    If the only thing stopping an edit were a failing dispatch, this file would
    pass against an implementation with no suite check in it at all.
    """
    dispatcher = StubDispatcher(default=completion("this is in policy"))
    monkeypatch.setattr(gate_module, "dispatch", dispatcher)
    monkeypatch.setattr(gate_module, "check_spend_ceiling", allow_ceiling)
    return dispatcher


async def _propose(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    detector: DetectorId,
    family: RemedyFamily,
) -> None:
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        finding_id, _ = await repository.open_or_bump_finding(
            db,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            anomaly=Anomaly(detector_id=detector, params={}),
            evidence_line=None,
            now=day(3),
        )
        prompts = await list_released_prompts(db, WORKSPACE_A)
        revision = await get_revision(db, VERSION_ID)

    entry = Triaged(
        anomaly=Anomaly(detector_id=detector, params={}), rank=1, family=family
    )
    await sweep_module._propose(
        app_sessionmaker, WORKSPACE_A, prompts[0], revision, [(entry, finding_id)], day(3)
    )


async def _proposals(migrate_engine: AsyncEngine) -> list[Any]:
    async with migrate_engine.begin() as connection:
        return (
            (await connection.execute(PROPOSALS, {"prompt_id": PROMPT_ID})).mappings().all()
        )


@pytest.mark.parametrize("family", list(RemedyFamily), ids=str)
async def test_no_family_produces_an_edit_when_there_is_nothing_to_gate_against(
    family: RemedyFamily,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_released_prompt_with_no_suite: None,
    a_dispatcher_that_would_pass: StubDispatcher,
) -> None:
    """**Every family, and the answer is the same one every time.**

    The parametrisation is the assertion. A check that lived inside the transform
    would refuse `add_length_rule` and let `tighten_refusal_block` through, and a
    test written against one family would never see it.
    """
    await _propose(app_sessionmaker, DETECTOR_FOR_FAMILY[family], family)

    rows = await _proposals(migrate_engine)

    assert [row["remedy_kind"] for row in rows] == ["case"]
    assert rows[0]["candidate_body"] is None
    assert rows[0]["remedy_family"] is None
    assert rows[0]["gate_run_id"] is None


@pytest.mark.parametrize("family", list(RemedyFamily), ids=str)
async def test_nothing_was_dispatched_to_find_that_out(
    family: RemedyFamily,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    a_released_prompt_with_no_suite: None,
    a_dispatcher_that_would_pass: StubDispatcher,
) -> None:
    """The suite check comes FIRST, before the transform and before the money.

    Ordering is a cost decision and a correctness one. Building a candidate and
    dispatching a suite that does not exist would spend the workspace's provider
    credit to discover something a single query already knew — every night, on
    every prompt without a suite, which in a young workspace is most of them.
    """
    await _propose(app_sessionmaker, DETECTOR_FOR_FAMILY[family], family)

    assert a_dispatcher_that_would_pass.calls == []


async def test_a_suite_with_no_cases_is_not_a_suite(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_released_prompt_with_no_suite: None,
    a_dispatcher_that_would_pass: StubDispatcher,
) -> None:
    """*Has a suite* and *has something to run* are different questions.

    An empty suite is a row somebody created and never filled in. Gating against
    it would produce a result that passed every case it was given — zero of them
    — and a proposal whose evidence card read *0/0 cases pass*, which is a
    stronger-looking claim than *no suite* and a weaker one.
    """
    await seed_suite(migrate_engine, case_count=0)

    await _propose(
        app_sessionmaker, DetectorId.TRUNCATION_RISING, RemedyFamily.ADD_LENGTH_RULE
    )

    rows = await _proposals(migrate_engine)
    assert [row["remedy_kind"] for row in rows] == ["case"]
    assert a_dispatcher_that_would_pass.calls == []


async def test_the_schema_refuses_an_ungated_edit_even_if_the_code_offered_one(
    migrate_engine: AsyncEngine, a_released_prompt_with_no_suite: None
) -> None:
    """SR-3 in the engine, so the rule survives the code that implements it.

    Every assertion above is about `_propose`'s behaviour, and behaviour is what
    changes when somebody is in a hurry. `ck_improvement_proposal_an_edit_is_gated`
    is what makes an ungated edit unwritable — by this module, by a migration, by
    a future caller that had a good reason.
    """
    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO improvement.finding
                    (id, workspace_id, prompt_id, detector_id, severity, params,
                     first_seen, last_seen, occurrence_count, status, created_at)
                VALUES
                    ('fnd_01J000000000000NOSUITE1', :workspace_id, :prompt_id,
                     'truncation_rising', 'warning', '{}'::jsonb,
                     :now, :now, 1, 'open', :now)
                """
            ),
            {"workspace_id": WORKSPACE_A, "prompt_id": PROMPT_ID, "now": day(3)},
        )

    with pytest.raises(IntegrityError) as refusal:
        async with migrate_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO improvement.proposal
                        (id, workspace_id, prompt_id, finding_id, remedy_kind,
                         remedy_family, candidate_body, gate_run_id, gate_delta,
                         status, expires_at, created_at)
                    VALUES
                        ('prp_01J000000000000NOSUITE1', :workspace_id, :prompt_id,
                         'fnd_01J000000000000NOSUITE1', 'edit', 'add_length_rule',
                         '<system>x</system>', NULL, NULL, 'open', :expires_at, :now)
                    """
                ),
                {
                    "workspace_id": WORKSPACE_A,
                    "prompt_id": PROMPT_ID,
                    "expires_at": day(17),
                    "now": day(3),
                },
            )

    assert "ck_improvement_proposal_an_edit_is_gated" in str(refusal.value)

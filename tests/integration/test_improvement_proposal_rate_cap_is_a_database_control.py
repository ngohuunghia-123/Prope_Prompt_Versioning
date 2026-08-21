"""AC-3 / SR-2 — one open proposal per prompt, refused by the DATABASE.

**The rate cap is the difference between a queue and a nag**, and the reason it
is a constraint rather than a service check is the reason every other invariant
in this product is: a check in the sweep is a check the sweep can skip. The sweep
is a background job that runs unattended against every workspace; a retry, a
second worker, or a future caller that opened a proposal from somewhere else
would each produce a second offer for the same prompt, and nobody would see it
until a person opened an inbox with the same suggestion twice.

**Two partial unique indexes carry two different jobs and both are asserted here.**
`uq_improvement_proposal_one_open_per_prompt` is the cap. Its sibling on
`finding` — `uq_improvement_finding_one_open_per_detector` — is what turns a
signal that fires every day for a fortnight into ONE row with an occurrence count
of fourteen, which is deck 6 slide 64's alert fatigue answered in the data model
rather than in the renderer.

**`WHERE status = 'open'` is what makes both liveable.** A prompt whose proposal
was dismissed in March can have another in April; a detector that resolved can
fire again. A total unique index would have made the cap permanent, which is a
different and much worse product.

The strongest form of this test bypasses the repository entirely: two raw inserts
as the migrate role, expecting the engine to refuse the second. A test written
only against `open_proposal` would pass just as well if the `ON CONFLICT` clause
were the only thing standing between a person and a duplicate.
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.prompt_improvement import repository
from prope.prompt_improvement.domain import Anomaly, DetectorId, RemedyKind
from tests.evaluation import PROMPT_ID, WORKSPACE_A, day, seed_owner
from tests.prompt_registry import approve, release, seed_prompt, seed_revision

SESSION_ID = "ses_improvement_ratecap_0001"

VERSION_ID = "rev_01J0000000000000RATECAP1"

FINDING_ONE = "fnd_01J000000000000000FIND01"
FINDING_TWO = "fnd_01J000000000000000FIND02"

INSERT_FINDING = text(
    """
    INSERT INTO improvement.finding
        (id, workspace_id, prompt_id, detector_id, severity, params, evidence_line,
         first_seen, last_seen, occurrence_count, status, created_at)
    VALUES
        (:id, :workspace_id, :prompt_id, :detector_id, 'warning', '{}'::jsonb, NULL,
         :now, :now, 1, :status, :now)
    """
)

INSERT_PROPOSAL = text(
    """
    INSERT INTO improvement.proposal
        (id, workspace_id, prompt_id, finding_id, remedy_kind, remedy_family,
         candidate_body, gate_run_id, gate_delta, status, decided_by, decided_at,
         expires_at, created_at)
    VALUES
        (:id, :workspace_id, :prompt_id, :finding_id, 'note', NULL,
         NULL, NULL, NULL, :status, :decided_by, :decided_at, :expires_at, :now)
    """
)

COUNT_PROPOSALS = text(
    "SELECT count(*) FROM improvement.proposal WHERE prompt_id = :prompt_id"
)

PROPOSAL_STATUSES = text(
    "SELECT status FROM improvement.proposal WHERE prompt_id = :prompt_id ORDER BY id"
)

FINDING_ROW = text(
    """
    SELECT occurrence_count, first_seen, last_seen, evidence_line
      FROM improvement.finding
     WHERE id = :id
    """
)

INDEX_DEFINITIONS = text(
    """
    SELECT indexname, indexdef
      FROM pg_indexes
     WHERE schemaname = 'improvement'
       AND indexname LIKE 'uq_improvement%'
     ORDER BY indexname
    """
)


@pytest.fixture
async def a_released_prompt(migrate_engine: AsyncEngine) -> None:
    """The rows the foreign keys need. The subject is the index, not the seeding."""
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, VERSION_ID, status="Approved")
    await approve(migrate_engine, VERSION_ID)
    await release(migrate_engine, PROMPT_ID, VERSION_ID)


async def _finding(engine: AsyncEngine, finding_id: str, detector: DetectorId, status: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            INSERT_FINDING,
            {
                "id": finding_id,
                "workspace_id": WORKSPACE_A,
                "prompt_id": PROMPT_ID,
                "detector_id": str(detector),
                "status": status,
                "now": day(3),
            },
        )


async def _proposal(engine: AsyncEngine, proposal_id: str, finding_id: str, status: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            INSERT_PROPOSAL,
            {
                "id": proposal_id,
                "workspace_id": WORKSPACE_A,
                "prompt_id": PROMPT_ID,
                "finding_id": finding_id,
                "status": status,
                "decided_by": None if status in ("open", "expired") else "usr_deciding_actor",
                "decided_at": None if status in ("open", "expired") else day(4),
                "expires_at": day(17),
                "now": day(3),
            },
        )


async def test_a_second_open_proposal_is_refused_by_the_engine(
    migrate_engine: AsyncEngine, a_released_prompt: None
) -> None:
    """**No application code involved.** Two inserts, one refusal.

    This is the assertion SR-2 is actually about. The repository's ``ON CONFLICT
    DO NOTHING`` is a convenience that turns the refusal into a ``None`` return;
    what stops a duplicate reaching somebody's inbox is the index underneath it,
    and only a statement that skips the repository can prove the index is there.
    """
    await _finding(migrate_engine, FINDING_ONE, DetectorId.TRUNCATION_RISING, "open")
    await _finding(migrate_engine, FINDING_TWO, DetectorId.FALLBACK_RISING, "open")

    await _proposal(migrate_engine, "prp_01J00000000000000PROP01", FINDING_ONE, "open")

    with pytest.raises(IntegrityError) as refusal:
        await _proposal(migrate_engine, "prp_01J00000000000000PROP02", FINDING_TWO, "open")

    assert "uq_improvement_proposal_one_open_per_prompt" in str(refusal.value)


async def test_a_decided_proposal_frees_the_slot(
    migrate_engine: AsyncEngine, a_released_prompt: None
) -> None:
    """``WHERE status = 'open'`` — the clause that makes the cap liveable.

    A prompt whose proposal was dismissed in March can have another in April. A
    total unique index would have made the cap permanent, which is a different
    product: one that offers a suggestion once, is told no, and then has nothing
    to say about that prompt for the rest of its life.
    """
    await _finding(migrate_engine, FINDING_ONE, DetectorId.TRUNCATION_RISING, "resolved")
    await _finding(migrate_engine, FINDING_TWO, DetectorId.FALLBACK_RISING, "open")

    await _proposal(migrate_engine, "prp_01J00000000000000PROP03", FINDING_ONE, "dismissed")
    await _proposal(migrate_engine, "prp_01J00000000000000PROP04", FINDING_TWO, "open")

    async with migrate_engine.begin() as connection:
        statuses = (
            (await connection.execute(PROPOSAL_STATUSES, {"prompt_id": PROMPT_ID}))
            .scalars()
            .all()
        )

    assert sorted(statuses) == ["dismissed", "open"]


async def test_the_repository_reports_the_refusal_as_a_missing_id(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_released_prompt: None,
) -> None:
    """``open_proposal`` returns ``None`` rather than raising, and the sweep reads that.

    A raise would be correct behaviour for a bug and wrong behaviour for this: the
    slot being taken is the normal, expected outcome on any prompt that already
    has an outstanding offer, and a sweep that aborted a workspace over it would
    stop measuring everything downstream of the first busy prompt.
    """
    await _finding(migrate_engine, FINDING_ONE, DetectorId.TRUNCATION_RISING, "open")
    await _finding(migrate_engine, FINDING_TWO, DetectorId.FALLBACK_RISING, "open")

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        first = await repository.open_proposal(
            db,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            finding_id=FINDING_ONE,
            remedy_kind=RemedyKind.NOTE,
            remedy_family=None,
            candidate_body=None,
            gate_run_id=None,
            gate_delta=None,
            expires_at=day(17),
            now=day(3),
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        second = await repository.open_proposal(
            db,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            finding_id=FINDING_TWO,
            remedy_kind=RemedyKind.NOTE,
            remedy_family=None,
            candidate_body=None,
            gate_run_id=None,
            gate_delta=None,
            expires_at=day(17),
            now=day(3),
        )

    assert first is not None
    assert second is None

    async with migrate_engine.begin() as connection:
        count = (
            await connection.execute(COUNT_PROPOSALS, {"prompt_id": PROMPT_ID})
        ).scalar_one()
    assert count == 1


async def test_a_signal_that_fires_every_day_is_one_row_with_a_count(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_released_prompt: None,
) -> None:
    """The dedupe index, which is the other half of not being a nag.

    Fourteen rows saying the same thing is deck 6 slide 64's alert fatigue
    produced by the data model. One row saying *seen 14 times*, with the first
    and last timestamps intact, is the same information in the shape a person can
    act on — and the occurrence count is only trustworthy because the index made
    the second write an UPDATE rather than an INSERT.
    """
    ids: list[str] = []
    anomaly = Anomaly(
        detector_id=DetectorId.TRUNCATION_RISING, params={"share": 0.3, "prior_share": 0.02}
    )

    for offset, evidence in enumerate(["một phần ba câu trả lời bị cắt", None, "vẫn bị cắt"]):
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            finding_id, occurrences = await repository.open_or_bump_finding(
                db,
                workspace_id=WORKSPACE_A,
                prompt_id=PROMPT_ID,
                anomaly=anomaly,
                evidence_line=evidence,
                now=day(3 + offset),
            )
        ids.append(finding_id)
        assert occurrences == offset + 1

    assert len(set(ids)) == 1, "the same detector opened more than one row"

    async with migrate_engine.begin() as connection:
        row = (await connection.execute(FINDING_ROW, {"id": ids[0]})).mappings().one()

    assert row["occurrence_count"] == 3
    assert row["first_seen"] == day(3)
    assert row["last_seen"] == day(5)
    # A sweep that produced no sentence must not erase the one that did. The
    # `COALESCE` is what keeps a degraded triage pass from silently blanking an
    # evidence line somebody has already read.
    assert row["evidence_line"] == "vẫn bị cắt"


async def test_both_indexes_are_partial_on_the_open_status(migrate_engine: AsyncEngine) -> None:
    """Read off `pg_indexes`, because the predicate is the whole design.

    Without `WHERE status = 'open'` both indexes are still unique, both still
    stop a duplicate, and both quietly become permanent: a dismissed finding
    could never reopen and a decided proposal could never be replaced. The
    failure would look like the module going quiet about a prompt, which is
    indistinguishable from the prompt behaving.
    """
    async with migrate_engine.begin() as connection:
        rows: list[Any] = (await connection.execute(INDEX_DEFINITIONS)).mappings().all()

    definitions = {row["indexname"]: row["indexdef"] for row in rows}

    assert "uq_improvement_proposal_one_open_per_prompt" in definitions
    assert "uq_improvement_finding_one_open_per_detector" in definitions

    for name, definition in definitions.items():
        assert "UNIQUE" in definition, name
        assert "status = 'open'" in definition.replace("::text", ""), name

    # The cap's key is the PROMPT, not the finding: one offer per prompt, whatever
    # fired. Keyed on `finding_id` it would allow twelve open proposals on a badly
    # degraded prompt, which is the day somebody stops opening the inbox.
    cap = definitions["uq_improvement_proposal_one_open_per_prompt"].replace(" ", "")
    assert "(workspace_id,prompt_id)" in cap, cap

    dedupe = definitions["uq_improvement_finding_one_open_per_detector"].replace(" ", "")
    assert "(workspace_id,prompt_id,detector_id)" in dedupe, dedupe

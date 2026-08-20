"""AC-7 — the first sweep on a workspace measures and reports a total. No findings.

**Because the first pass is the only one that can produce a backlog**, and a
backlog delivered as a queue is a queue nobody ever opens. A workspace that has
been running for a year and installs this module has a year of accumulated drift;
the honest first act is to say *we looked at 340 prompts and 41 are showing
something*, not to open 41 rows and let somebody discover the shape of the
problem by scrolling. Deck 6 slide 64's alert fatigue, avoided on day one rather
than apologised for on day three.

**Tomorrow's pass opens them one recurrence at a time**, against a person who has
already been told what to expect. That is the whole reason the module tolerates
losing a day of findings: the first day's findings were never the useful ones.

**`is_first_sweep` is computed from the presence of a prior `improvement.sweep`
row, and that is why `sweep` has no DELETE grant.** A retention job that tidied
sweep rows away would make a dormant workspace look new, and the module would
silently repeat its first-pass behaviour — measuring, reporting a total nobody
reads, and opening nothing. The privilege is the guarantee; a policy would be a
comment. That grant is asserted here beside the behaviour that depends on it,
because the two are one decision.
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.prompt_improvement import sweep as sweep_module
from prope.prompt_improvement.triage import _untriaged
from tests.evaluation import PROMPT_ID, WORKSPACE_A, day, seed_bound_revision, seed_owner
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_improvement_first_000001"

VERSION_ID = "rev_01J000000000000000FIRST1"

BODY = "<system>Bạn là trợ lý nội bộ của ACME.</system>"

APPROVED_PROFILE = {
    "audience": "internal",
    "untrusted_input": "none",
    "acts": "answers_only",
    "sensitivity": "synthetic",
}

SWEEPS = text(
    """
    SELECT prompts_scanned, findings_opened, is_first_sweep, window_start, window_end
      FROM improvement.sweep
     WHERE workspace_id = :workspace_id
     ORDER BY completed_at
    """
)

COUNT_FINDINGS = text(
    "SELECT count(*) FROM improvement.finding WHERE workspace_id = :workspace_id"
)

APP_PRIVILEGES = text(
    """
    SELECT privilege_type
      FROM information_schema.table_privileges
     WHERE table_schema = 'improvement'
       AND table_name = :table_name
       AND grantee = 'prope_app'
     ORDER BY privilege_type
    """
)

EDIT_PROFILE = text(
    "UPDATE registry.prompt_property SET audience = 'public' WHERE id = :id"
)


@pytest.fixture(autouse=True)
def a_deterministic_triage(monkeypatch: pytest.MonkeyPatch) -> None:
    """The production degradation path, used deliberately. See AC-9's note."""

    async def untriaged(anomalies: Any, **_: Any) -> Any:
        return _untriaged(anomalies)

    monkeypatch.setattr(sweep_module, "triage_anomalies", untriaged)


@pytest.fixture
async def a_workspace_with_one_degraded_prompt(migrate_engine: AsyncEngine) -> None:
    """One released prompt whose declaration moved after release.

    Profile drift rather than a ledger detector, because it needs no traffic: a
    fixture that seeded call records to make this file's subject reachable would
    make a failure in the window SQL read as a failure in the first-pass rule.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine, **APPROVED_PROFILE)
    await seed_bound_revision(
        migrate_engine,
        version_id=VERSION_ID,
        body=BODY,
        status="Approved",
        **APPROVED_PROFILE,
    )
    await approve(migrate_engine, VERSION_ID)
    await release(migrate_engine, PROMPT_ID, VERSION_ID)
    async with migrate_engine.begin() as connection:
        await connection.execute(EDIT_PROFILE, {"id": PROMPT_ID})


async def _sweeps(migrate_engine: AsyncEngine) -> list[Any]:
    async with migrate_engine.begin() as connection:
        return (
            (await connection.execute(SWEEPS, {"workspace_id": WORKSPACE_A}))
            .mappings()
            .all()
        )


async def _finding_count(migrate_engine: AsyncEngine) -> int:
    async with migrate_engine.begin() as connection:
        return (
            await connection.execute(COUNT_FINDINGS, {"workspace_id": WORKSPACE_A})
        ).scalar_one()


async def test_the_first_pass_writes_a_summary_row_and_no_findings(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_workspace_with_one_degraded_prompt: None,
) -> None:
    """It looked, it counted, and it opened nothing.

    ``prompts_scanned`` proves the pass was not vacuous — a sweep that found no
    prompts would also open no findings and would satisfy a weaker assertion
    perfectly.
    """
    await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(10))

    rows = await _sweeps(migrate_engine)
    assert len(rows) == 1
    assert rows[0]["is_first_sweep"] is True
    assert rows[0]["prompts_scanned"] == 1
    assert rows[0]["findings_opened"] == 0
    assert rows[0]["window_end"] > rows[0]["window_start"]

    assert await _finding_count(migrate_engine) == 0


async def test_the_second_pass_opens_what_the_first_only_counted(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_workspace_with_one_degraded_prompt: None,
) -> None:
    """The other half, so the first test is not passing because nothing works.

    A module that never opened a finding would satisfy the assertions above and
    would be exactly the implementation this pair exists to reject.
    """
    await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(10))
    await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(11))

    rows = await _sweeps(migrate_engine)
    assert [row["is_first_sweep"] for row in rows] == [True, False]
    assert rows[1]["findings_opened"] == 1

    assert await _finding_count(migrate_engine) == 1


async def test_a_workspace_with_nothing_wrong_still_records_that_it_was_swept(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """**The row is written whether or not anything was found**, and it must be.

    `is_first_sweep` is derived from the EXISTENCE of a prior row, so a sweep
    that only recorded itself when it had something to say would mark every
    healthy workspace as new forever — and the first prompt ever to degrade there
    would be counted and not opened, silently, on a workspace that had been
    watched for months.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine, **APPROVED_PROFILE)
    await seed_bound_revision(
        migrate_engine,
        version_id=VERSION_ID,
        body=BODY,
        status="Approved",
        **APPROVED_PROFILE,
    )
    await approve(migrate_engine, VERSION_ID)
    await release(migrate_engine, PROMPT_ID, VERSION_ID)

    await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(10))
    await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(11))

    rows = await _sweeps(migrate_engine)
    assert [row["is_first_sweep"] for row in rows] == [True, False]
    assert [row["findings_opened"] for row in rows] == [0, 0]
    assert await _finding_count(migrate_engine) == 0


async def test_the_app_role_cannot_delete_a_sweep_row(migrate_engine: AsyncEngine) -> None:
    """**Retention expressed as a privilege, because the row is load-bearing.**

    Every other table in this schema has a retention term. `improvement.sweep`
    has none, and the absence is deliberate: the rows are the module's memory of
    having looked, and forgetting one silently reverts a workspace to first-pass
    behaviour. A comment saying *do not delete these* would be a comment; a
    missing grant is a refusal.
    """
    async with migrate_engine.begin() as connection:
        granted = (
            (await connection.execute(APP_PRIVILEGES, {"table_name": "sweep"}))
            .scalars()
            .all()
        )

    assert set(granted) == {"SELECT", "INSERT"}, granted
    assert "DELETE" not in granted
    assert "UPDATE" not in granted, (
        "a sweep row records what one pass saw at one moment; rewriting it would make "
        "the module's own history unreadable"
    )

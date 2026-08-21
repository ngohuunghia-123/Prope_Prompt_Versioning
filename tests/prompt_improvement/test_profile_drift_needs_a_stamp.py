"""AC-9 — `profile_drift` fires when the profile is edited AFTER release, and not before.

**This is the payoff of ADR-0067's D-02, and the reason that decision cost a
migration.** *Serving the public; approved as internal* is a governance failure
that no diff and no eval suite can see: the body did not change, the suite still
passes, and the thing in production is answering a different population than the
one anybody reviewed it for. The only way to notice is to compare the property's
CURRENT declaration against the copy stamped onto the revision when it was
created — and without that stamp the comparison has nothing on its right-hand
side, so the detector is undetectable rather than merely unimplemented.

**No stamp means silence, never a guess.** A revision released before migration
0030 carries nothing, and the honest answer is that the comparison cannot be
made. Inferring the missing half from the body is exactly what A-163 forbids: the
profile is declared by a person, and a module that reconstructed it would be
deciding what a prompt is for on that person's behalf and then reporting the
difference from its own guess as a finding.

**It is note-only, and that follows from the same argument.** A declaration is a
person's to change, so the remedy is *go and look*, never a proposed edit. A
module that offered to rewrite a prompt because its stated audience moved would be
inferring the profile through the back door.

The unit-level arithmetic is asserted in AC-1. What this file adds is the half
that needed a database: that the sweep reads the declaration from
`registry.prompt_property` and the stamp from the RELEASED revision, and not
either one twice.
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.prompt_improvement import sweep as sweep_module
from prope.prompt_improvement.domain import DetectorId
from prope.prompt_improvement.triage import _untriaged, triage_anomalies
from tests.evaluation import PROMPT_ID, WORKSPACE_A, day, seed_bound_revision, seed_owner
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_improvement_drift_0000001"

VERSION_ID = "rev_01J000000000000000DRIFT1"

BODY = "<system>Bạn là trợ lý nội bộ của ACME.</system>"

#: What the prompt was approved under. Internal, no untrusted input, answers only.
APPROVED_PROFILE = {
    "audience": "internal",
    "untrusted_input": "none",
    "acts": "answers_only",
    "sensitivity": "synthetic",
}

FINDINGS = text(
    """
    SELECT detector_id, severity, params, occurrence_count
      FROM improvement.finding
     WHERE prompt_id = :prompt_id
     ORDER BY detector_id
    """
)

PROPOSALS = text("SELECT remedy_kind FROM improvement.proposal WHERE prompt_id = :prompt_id")

EDIT_PROFILE = text(
    "UPDATE registry.prompt_property SET audience = :audience WHERE id = :id"
)

UNSTAMP = text(
    """
    UPDATE registry.revision
       SET audience = 'undeclared', untrusted_input = 'undeclared',
           acts = 'undeclared', sensitivity = 'undeclared'
     WHERE version_id = :version_id
    """
)


@pytest.fixture(autouse=True)
def a_deterministic_triage(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model-free ranking, so this file is about the detector and not the model.

    ``_untriaged`` is not a stub — it is the production degradation path, the one
    that runs whenever the triage model is unavailable, and using it here means
    every assertion below holds on the worst day this module can have. The
    ranking is `detectors.DETECTORS` order; the evidence line is absent; the
    finding still stands, because the ``vi`` catalogue carries the sentence and
    the evidence is only the specificity on top of it.
    """
    monkeypatch.setattr(
        sweep_module, "triage_anomalies", lambda anomalies, **_: _async(_untriaged(anomalies))
    )


async def _async(value: Any) -> Any:
    return value


@pytest.fixture
async def a_prompt_released_under_a_declared_profile(migrate_engine: AsyncEngine) -> None:
    """Declared, approved and released — with the property and the stamp AGREEING."""
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


async def _sweep_twice(app_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Two passes, because the first one on a workspace only ever reports a total.

    A-162's inversion is what makes this necessary and AC-7 is what asserts it.
    Here it is just the cost of reaching the second pass, where findings are
    actually written.
    """
    await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(10))
    await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(11))


async def _findings(migrate_engine: AsyncEngine) -> list[Any]:
    async with migrate_engine.begin() as connection:
        return (
            (await connection.execute(FINDINGS, {"prompt_id": PROMPT_ID})).mappings().all()
        )


async def test_a_prompt_serving_under_the_profile_it_was_approved_with_is_silent(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_prompt_released_under_a_declared_profile: None,
) -> None:
    """**Empty is the success condition** (A-162's inversion).

    The control case, and it is not a formality: a detector that fired whenever a
    profile existed would satisfy the positive test below perfectly and would
    open a finding on every governed prompt in the product on its first night.
    """
    await _sweep_twice(app_sessionmaker)

    assert await _findings(migrate_engine) == []


async def test_editing_the_declaration_after_release_opens_the_finding(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_prompt_released_under_a_declared_profile: None,
) -> None:
    """*Serving the public; approved as internal.* One axis moved, one finding.

    ``params`` names which axis and in which direction, because *"the profile
    changed"* is not actionable and *"audience: internal → public"* is — and
    because the reviewer's next act is to create a revision so the thing in
    production is re-approved under what it now claims to be.
    """
    async with migrate_engine.begin() as connection:
        await connection.execute(EDIT_PROFILE, {"audience": "public", "id": PROMPT_ID})

    await _sweep_twice(app_sessionmaker)

    rows = await _findings(migrate_engine)
    assert [row["detector_id"] for row in rows] == [str(DetectorId.PROFILE_DRIFT)]
    assert rows[0]["severity"] == "warning"
    assert rows[0]["params"]["axes"] == {
        "audience": {"stamped": "internal", "declared": "public"}
    }


async def test_an_undeclared_stamp_is_a_declaration_nobody_made_and_still_drifts(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_prompt_released_under_a_declared_profile: None,
) -> None:
    """**`undeclared` is a value, not an absence** — and that is A-163's whole point.

    Migration 0030 seeds a sentinel rather than a NULL precisely so that *nobody
    has said* is a state the product can render, distinguishable from *this axis
    does not apply*. Which means a revision stamped `undeclared` and a property
    that now says `public` really have drifted: what is serving was approved
    under no stated purpose, and somebody has since stated one. Reporting that is
    correct and is not migration noise — the finding says *go and re-approve it
    under what you now say it is*.

    The case where the detector genuinely cannot answer is the one where there is
    nothing on the right at all, and `profile_drift(declared, None)` returning
    `None` is asserted in AC-1. It cannot be reached from here: a released prompt
    has a released revision by BR-03's foreign key.
    """
    async with migrate_engine.begin() as connection:
        await connection.execute(EDIT_PROFILE, {"audience": "public", "id": PROMPT_ID})
        await connection.execute(UNSTAMP, {"version_id": VERSION_ID})

    await _sweep_twice(app_sessionmaker)

    rows = await _findings(migrate_engine)
    assert [row["detector_id"] for row in rows] == [str(DetectorId.PROFILE_DRIFT)]
    # All four axes moved, because all four were blanked. The finding names every
    # one of them rather than the first — a reviewer re-approving needs the whole
    # difference, not a sample of it.
    axes = rows[0]["params"]["axes"]
    assert set(axes) == {"audience", "untrusted_input", "acts", "sensitivity"}
    assert axes["audience"] == {"stamped": "undeclared", "declared": "public"}


async def test_the_finding_carries_no_proposal_to_edit_the_prompt(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_prompt_released_under_a_declared_profile: None,
) -> None:
    """Note-only, because a declaration is a person's to change.

    The remedy for *serving the public; approved as internal* is somebody
    deciding which of the two is right. A module that proposed a body edit here
    would be inferring the profile through the back door — A-163's ban, arriving
    as a helpful suggestion.
    """
    async with migrate_engine.begin() as connection:
        await connection.execute(EDIT_PROFILE, {"audience": "public", "id": PROMPT_ID})

    await _sweep_twice(app_sessionmaker)

    async with migrate_engine.begin() as connection:
        kinds = (
            (await connection.execute(PROPOSALS, {"prompt_id": PROMPT_ID})).scalars().all()
        )

    assert "edit" not in kinds


async def test_a_recurring_drift_is_one_row_with_a_rising_count(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    a_prompt_released_under_a_declared_profile: None,
) -> None:
    """Nobody has acted on it, so it is still true — and still ONE row.

    Profile drift is the finding most likely to sit unaddressed for weeks, since
    resolving it means creating a revision and getting it approved again. Three
    nights of the same fact must read as *seen 3 times*, not as three things
    wrong.
    """
    async with migrate_engine.begin() as connection:
        await connection.execute(EDIT_PROFILE, {"audience": "public", "id": PROMPT_ID})

    for offset in range(4):
        await sweep_module.sweep_workspace(app_sessionmaker, WORKSPACE_A, now=day(10 + offset))

    rows = await _findings(migrate_engine)
    assert len(rows) == 1
    # Four passes, the first of which only measured. Three recurrences.
    assert rows[0]["occurrence_count"] == 3


async def test_triage_degrades_rather_than_raising_when_no_model_is_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The autouse fixture above uses the degraded path, so prove it is real.

    A sweep is a background job with nobody watching. If triage raised on a bad
    model, one workspace's unreachable provider would stop that workspace being
    measured at all — and the symptom would be an empty inbox, which is
    indistinguishable from every prompt behaving.
    """
    from prope.prompt_improvement import triage as triage_module
    from prope.prompt_improvement.domain import Anomaly

    async def unavailable() -> Any:
        raise RuntimeError("no model configured")

    monkeypatch.setattr(triage_module, "_load_agent", unavailable)

    anomalies = (
        Anomaly(detector_id=DetectorId.FALLBACK_RISING, params={"share": 0.3}),
        Anomaly(detector_id=DetectorId.PROFILE_DRIFT, params={"axes": {}}),
    )

    triaged = await triage_anomalies(anomalies, prompt_title="x", prompt_body=BODY)

    assert [entry.anomaly.detector_id for entry in triaged] == [
        DetectorId.FALLBACK_RISING,
        DetectorId.PROFILE_DRIFT,
    ]
    assert all(entry.evidence is None for entry in triaged)
    assert all(entry.family is None for entry in triaged)

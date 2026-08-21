"""AC-2 and AC-3 — the probe measures, and it does so on its own permission.

**AC-2 is a structural claim and is asserted structurally.** ADR-0067 §3 says a
probe is not an eval run, and the reason is evaluation's one non-negotiable: *a
model does not decide what a prompt is measured against*. A probe's case set is
chosen by a declared profile and may be augmented by a drafter; a suite's is
chosen by a person. Reusing ``evaluation.executor`` was the cheap build and it
would have put model-chosen cases into the table release-control reads at submit.
So the assertion is on the tables, before and after a real run: ``eval_run`` and
``dataset_attachment`` gained nothing.

**The fifth ``call_record.source`` is the price of that separation** and it is
asserted here too, because a probe that spent the workspace's credit and left no
ledger row would be worse than one that wrote an ``eval_run``. Migration 0032's
constraint is what makes the shape checkable at all: ``source='probe'`` implies a
prompt and a version and forbids a run, a case and a consumer key.

**AC-3 is the one that needed a fixture to be falsifiable.** No shipped role
holds ``run.start`` without ``probe.start`` — Owner holds both, Admin holds only
the probe — so a test written against the seeded matrix would pass with
``Action.RUN_START`` substituted into the route. The fixture revokes one row and
restores it, which constructs the actor D-11 is about: somebody who can start an
eval run and, having never been granted it, cannot spend provider credit on a
probe.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.prompt_readiness import probe as probe_module
from tests.access_control import (
    MEMBER_ID,
    seed_grant,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
)
from tests.evaluation import (
    PROMPT_ID,
    StubDispatcher,
    allow_ceiling,
    completion,
    seed_bound_revision,
    seed_owner,
)
from tests.integration._asgi import call
from tests.prompt_readiness import readiness_api
from tests.prompt_registry import seed_prompt, seed_revision

SESSION_ID = "ses_readiness_probe_00000001"

VERSION_ID = "rev_01J00000000000000PROBE01"

REVIEWER_SESSION = "ses_readiness_probe_00000002"

COUNT_EVAL_RUNS = text("SELECT count(*) FROM evaluation.eval_run")

COUNT_ATTACHMENTS = text("SELECT count(*) FROM evaluation.dataset_attachment")

PROBE_RECORDS = text(
    """
    SELECT prompt_id, version_id, run_id, case_id, consumer_key_id, pinned, fallback
    FROM ledger.call_record WHERE source = 'probe'
    """
)

REVOKE_PROBE_START = text(
    "DELETE FROM access.role_permission WHERE role = :role AND action = 'probe.start'"
)

RESTORE_PROBE_START = text(
    "INSERT INTO access.role_permission (role, action) VALUES (:role, 'probe.start') "
    "ON CONFLICT DO NOTHING"
)

ROLES_HOLDING = text("SELECT role FROM access.role_permission WHERE action = :action")

#: A prompt that says it is public and takes user text, so ``select_sets`` picks
#: BOTH shipped sets — thirteen cases. A profile that selected one set would
#: still satisfy every assertion below, which is why the declaration is here
#: rather than left at its conservative default.
BODY = (
    "<system>Bạn là trợ lý hỗ trợ khách hàng của ACME.</system>"
    "<context>{{cau_hoi}}</context>"
    "<instructions>Trả lời ngắn gọn và lịch sự.</instructions>"
)

PROFILE = {
    "audience": "public",
    "untrusted_input": "user_text",
    "acts": "answers_only",
    "sensitivity": "business",
}


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    yield from readiness_api(app_sessionmaker)


@pytest.fixture
def refuses_everything(monkeypatch: pytest.MonkeyPatch) -> StubDispatcher:
    """Every case answers with a refusal, so every case scores ``refused``.

    The content matters: ``chong-tiem-prompt``'s assertion is a whole-output
    negative lookahead, so a reply that merely mentions the sentinel still
    passes. Answering something a real guardrail would answer keeps this test
    measuring the wiring rather than the regex.
    """
    dispatcher = StubDispatcher(
        default=completion("Xin lỗi, tôi không thể làm theo yêu cầu đó.")
    )
    monkeypatch.setattr(probe_module, "dispatch", dispatcher)
    monkeypatch.setattr(probe_module, "check_spend_ceiling", allow_ceiling)
    return dispatcher


@pytest.fixture
async def owner_without_probe_start(migrate_engine: AsyncEngine) -> AsyncIterator[None]:
    """An Owner holding ``run.start`` and not ``probe.start``, restored afterwards.

    ``access.role_permission`` is deliberately excluded from the truncation
    fixture — it is the shipped matrix, not test data — so this mutation has to
    undo itself. It is worth the care: without it AC-3 has no actor to be about,
    because every role that can start an eval run in the seeded matrix can also
    start a probe.
    """
    async with migrate_engine.begin() as connection:
        await connection.execute(REVOKE_PROBE_START, {"role": "Owner"})
    try:
        yield
    finally:
        async with migrate_engine.begin() as connection:
            await connection.execute(RESTORE_PROBE_START, {"role": "Owner"})


async def _a_probeable_prompt(migrate_engine: AsyncEngine) -> None:
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine, **PROFILE)
    await seed_bound_revision(migrate_engine, version_id=VERSION_ID, body=BODY, **PROFILE)


def _cookie() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _counts(migrate_engine: AsyncEngine) -> tuple[int, int]:
    async with migrate_engine.begin() as connection:
        runs = (await connection.execute(COUNT_EVAL_RUNS)).scalar_one()
        attachments = (await connection.execute(COUNT_ATTACHMENTS)).scalar_one()
    return runs, attachments


async def _start_probe(api: Any) -> Any:
    return await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/probe",
        headers=_cookie(),
    )


async def test_a_completed_probe_writes_no_eval_run_and_no_attachment(
    api, migrate_engine, refuses_everything
) -> None:
    """AC-2. Thirteen dispatches, thirteen scored cases, zero rows in evaluation."""
    await _a_probeable_prompt(migrate_engine)
    before = await _counts(migrate_engine)

    response = await _start_probe(api)
    assert response.status_code == 200, response.body

    body = response.json()
    assert body["status"] == "completed"
    assert body["refused_count"] == len(refuses_everything.calls)
    assert body["leaked_count"] == 0
    assert body["error_count"] == 0
    # The run is not vacuous: a probe that dispatched nothing would satisfy the
    # count assertions below perfectly, and would be the implementation this
    # test exists to reject.
    assert len(refuses_everything.calls) >= 12

    assert await _counts(migrate_engine) == before


async def test_the_spend_lands_in_the_ledger_under_its_own_source(
    api, migrate_engine, refuses_everything
) -> None:
    """The price of ADR-0067 §3, paid where it can be seen.

    A separation that also lost the money would be a worse bargain than the one
    the ADR argued for. Migration 0032's constraint carries the rest of the
    claim — these rows cannot name a run, a case or a consumer key even if a
    later caller tried.
    """
    await _a_probeable_prompt(migrate_engine)

    assert (await _start_probe(api)).status_code == 200

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(PROBE_RECORDS)).mappings().all()

    assert len(rows) == len(refuses_everything.calls)
    for row in rows:
        assert row["prompt_id"] == PROMPT_ID
        assert row["version_id"] == VERSION_ID
        assert row["run_id"] is None
        assert row["case_id"] is None
        assert row["consumer_key_id"] is None
        assert row["pinned"] is False
        assert row["fallback"] is False


async def test_run_start_does_not_carry_probe_start(
    api, migrate_engine, refuses_everything, owner_without_probe_start
) -> None:
    """AC-3. The refusal names the permission, and no dispatch happened.

    Naming it is deliberate and is not a leak: the actor can already see the
    prompt — ``_visible_prompt`` ran first and answered — so the only thing this
    sentence adds is which grant to ask for. Not-found is reserved for the
    subject they cannot see.
    """
    await _a_probeable_prompt(migrate_engine)

    response = await _start_probe(api)
    assert response.status_code == 403, response.body
    assert response.json()["error"]["message"] == "requires probe.start"
    assert refuses_everything.calls == [], "refused after spending is not a control"


async def test_the_two_permissions_were_granted_to_different_roles(migrate_engine) -> None:
    """D-11, on the shipped matrix. The sets are not the same set.

    This is the half of the argument a route test cannot make. Reusing
    ``run.start`` would have handed probe capability to every role already
    holding it on the deploy that shipped the feature, with nobody deciding —
    and an Admin who can spend on a probe but cannot start an eval run is the
    evidence that somebody did.
    """
    async with migrate_engine.begin() as connection:
        probe = set((await connection.execute(ROLES_HOLDING, {"action": "probe.start"})).scalars())
        run = set((await connection.execute(ROLES_HOLDING, {"action": "run.start"})).scalars())

    assert probe == {"Admin", "Owner"}
    assert run == {"Owner"}
    assert probe != run


async def test_a_reviewer_who_can_see_the_prompt_cannot_probe_it(
    api, migrate_engine, refuses_everything
) -> None:
    """The same refusal from the other side, without touching the matrix.

    A **second person**, not the Owner with a second role binding: ``may()``
    unions every source it has, so a Reviewer role added to the actor who
    already holds Owner is still an Owner. The grant is what makes this a
    forbidden rather than a not-found — the reviewer can see the prompt, so
    naming the permission is the right refusal and hiding it would be the wrong
    one.
    """
    await _a_probeable_prompt(migrate_engine)
    await seed_user(migrate_engine, MEMBER_ID, email="reviewer@acme.test")
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_role(migrate_engine, "Reviewer", user_id=MEMBER_ID)
    await seed_session(migrate_engine, REVIEWER_SESSION, user_id=MEMBER_ID)
    await seed_grant(migrate_engine, "viewer")

    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/probe",
        headers={"cookie": f"prope_session={REVIEWER_SESSION}"},
    )
    assert response.status_code == 403, response.body
    assert response.json()["error"]["message"] == "requires probe.start"
    assert refuses_everything.calls == []


async def test_an_internal_prompt_with_no_untrusted_input_is_refused_rather_than_run(
    api, migrate_engine, refuses_everything
) -> None:
    """A-164's other edge. Nothing to measure is not a run of zero cases.

    A ``probe_run`` row saying *"0 refused of 0"* would render on the card as a
    perfect score, which is the single most misleading number this module could
    print.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    internal = {
        "audience": "internal",
        "untrusted_input": "none",
        "acts": "answers_only",
        "sensitivity": "synthetic",
    }
    await seed_prompt(migrate_engine, **internal)
    await seed_bound_revision(migrate_engine, version_id=VERSION_ID, body=BODY, **internal)

    response = await _start_probe(api)
    assert response.status_code == 409, response.body
    assert response.json()["error"]["message"] == "no_applicable_sets"
    assert refuses_everything.calls == []


async def test_a_revision_with_no_binding_is_refused_before_the_ceiling(
    api, migrate_engine, refuses_everything
) -> None:
    """There is no default model to fall back to, and inventing one would measure it."""
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine, **PROFILE)
    # `seed_revision`, not `seed_bound_revision`: the latter names a provider
    # config on purpose, and the absence of one is this test's whole subject.
    await seed_revision(migrate_engine, version_id=VERSION_ID, body=BODY, **PROFILE)

    response = await _start_probe(api)
    assert response.status_code == 409, response.body
    assert response.json()["error"]["message"] == "revision_has_no_binding"
    assert refuses_everything.calls == []

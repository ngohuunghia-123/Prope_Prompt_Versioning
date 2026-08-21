"""The forwarded call becomes an inventory row, and only the right person sees it.

Four properties, and each one is a claim from a different document that would
otherwise only be a sentence:

*The write groups by fingerprint* (A-154). Three calls whose system messages
differ only in a date are ONE row with a count of three, and the interpolated
span never reaches the grouping key. This is the assumption most likely to be
wrong in the field, so it is asserted on the shape it fails in — too many rows.

*A sighting carries a body only when it changed one* (ADR-0060). Without that
rule this table is `ledger.call_body` under another name, at the same volume, on
the readable side of ADR-0018 — which is the one thing the ADR was written to
avoid.

*Visibility is the namespace* (ADR-0061, SR-1, SR-2). A second member with no
grant sees nothing and gets a **not-found**, byte-identical to an id that never
existed. Before namespaces were the unit of authorisation there was no rule this
module could have written, and that gap is what SR-2 recorded.

*Redact keeps the counts and loses the text* (SR-4). Including against a caller
that is still sending: the write path pins a redacted body rather than restoring
it, so the redaction survives the next request.
"""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.errors import install_error_envelope
from prope.prompt_observation.api import router as observation_router
from prope.prompt_observation.seams import ObservationDraft, record_observation
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    MEMBER_ID,
    WORKSPACE_A,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

ADMIN_SESSION = "ses_observation_000000001"

MEMBER_SESSION = "ses_observation_000000002"

NAMESPACE = "discovered"

KEY_ID = "key_01J000000000000000OBSERVE"

#: Three bodies that differ ONLY in the interpolated date. A-154 masks the
#: timestamp before hashing, so all three are one prompt with one fingerprint —
#: the case that would otherwise mint a fresh row on every single call, which is
#: the failure that makes an inventory useless rather than merely imprecise.
BODY_A = "You are a support agent for ACME. Today is 2026-08-14. Answer politely."

BODY_B = "You are a support agent for ACME. Today is 2026-08-15. Answer politely."

BODY_C = "You are a support agent for ACME. Today is 2026-08-16. Answer politely."

#: A genuinely DIFFERENT prompt — one word of instruction changed, outside any
#: masked span. It must not merge with the three above, and it is here so that
#: the grouping assertion is not vacuously satisfied by a rule that grouped
#: everything.
BODY_OTHER = "You are a support agent for ACME. Today is 2026-08-14. Answer briefly."

COUNT_SIGHTINGS_WITH_BODIES = text(
    "SELECT count(*) FROM observation.sighting WHERE body IS NOT NULL"
)

COUNT_SIGHTINGS = text("SELECT count(*) FROM observation.sighting")

GRANT_NAMESPACE = text(
    """
    INSERT INTO access.namespace_grant (workspace_id, namespace, grantee_user_id,
                                        level, granted_by, granted_at)
    VALUES (:workspace_id, :namespace, :grantee_user_id, 'viewer', :granted_by, now())
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    """This module's router on a bare application, with the real session boundary.

    The real ``authenticate_session`` and never a ``dependency_overrides`` seam,
    on prompt-registry's rule: the refusal shapes asserted below are only
    meaningful if the session came from a live row.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(observation_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


def _cookie(session_id: str) -> dict[str, str]:
    return {"cookie": f"prope_session={session_id}"}


async def _signed_in(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, ADMIN_SESSION)


async def _second_member(migrate_engine) -> None:  # noqa: ANN001
    """A colleague in the same workspace, with **no role binding at all**.

    The absence of a role is the whole design of this fixture, and it is not the
    stronger setup — it is the only one that isolates what ADR-0061 added.
    Every one of the four seeded roles holds `prompt.read` **workspace-wide**
    (migration 0006), so `visible_subject_filter` answers `ALL` for any actor
    carrying any of them, and the namespace filter is never reached. A colleague
    seeded as an Owner therefore sees every observation in the workspace, and a
    test that asserted otherwise would be asserting against the shipped
    permission matrix rather than against this module.

    That is a real and pre-existing property of the matrix rather than a hole
    ADR-0061 opened: namespace grants are a WIDENING mechanism — they let
    somebody in — and nothing in `may()` subtracts, by design (there is no
    deny-override branch and A-111 says why). Recorded on
    `prompt-observation.lock.yml` SR-2 so the promise there is not read as
    stronger than the matrix makes it, and it is OQ-006's to change, because
    which role holds which permission is a row in `access.role_permission` and
    not a code change.
    """
    await seed_user(migrate_engine, MEMBER_ID, email="second@acme.test")
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, MEMBER_SESSION, user_id=MEMBER_ID)


def _draft(body: str, call_id: str) -> ObservationDraft:
    return ObservationDraft(
        workspace_id=WORKSPACE_A,
        namespace=NAMESPACE,
        call_id=call_id,
        consumer_key_id=KEY_ID,
        upstream_model="gpt-4o",
        occurred_at=datetime.now(UTC),
        messages=[
            {"role": "system", "content": body},
            # Never stored, never hashed, never diffed. OQ-148 §4 asks whether an
            # end user's text should be persisted at all and this is the
            # conservative answer taken before the policy conversation starts.
            {"role": "user", "content": "where is my refund"},
        ],
    )


async def _observe(app_sessionmaker, *bodies: str) -> list[str | None]:  # noqa: ANN001
    return [
        await record_observation(app_sessionmaker, _draft(body, f"cal_obs{index:022d}"))
        for index, body in enumerate(bodies)
    ]


async def _inbox(api, session_id: str = ADMIN_SESSION) -> list[dict]:  # noqa: ANN001
    response = await call(api, "GET", "/api/v1/observations", headers=_cookie(session_id))
    assert response.status_code == 200, response.body
    return response.json()


async def test_three_calls_differing_only_in_a_date_are_one_row(
    api, migrate_engine, app_sessionmaker
) -> None:
    """A-154's grouping key, asserted on the shape it fails in.

    Too tight and one prompt becomes many rows, which is obvious in the first
    screenshot; too loose and two prompts merge into one, which is silently
    wrong. The rule leans tight, so the failure this asserts against is three
    rows where there should be one — the one a person would notice.
    """
    await _signed_in(migrate_engine)

    ids = await _observe(app_sessionmaker, BODY_A, BODY_B, BODY_C)
    assert len(set(ids)) == 1, ids
    assert ids[0] is not None

    rows = await _inbox(api)
    assert len(rows) == 1
    assert rows[0]["sighting_count"] == 3
    assert rows[0]["namespace"] == NAMESPACE
    assert rows[0]["status"] == "open"
    assert rows[0]["upstream_models"] == ["gpt-4o"]

    # And the rule is not "group everything". One word of instruction changed,
    # outside any masked span, is a different prompt and gets its own row —
    # without this half the assertion above would pass for a fingerprint that
    # ignored the body entirely.
    other = await _observe(app_sessionmaker, BODY_OTHER)
    assert other[0] not in ids
    assert len(await _inbox(api)) == 2


async def test_only_a_body_that_changed_is_stored(migrate_engine, app_sessionmaker) -> None:
    """ADR-0060's bound, and it is structural rather than a tuning knob.

    Four calls of the SAME body then one that differs: five sightings, and only
    the two that changed something carry text. `body_hash` is the exact hash, so
    a date moving still counts as a change — which is the point of storing the
    pair, since "the body changed on Tuesday" is answered by `fingerprint` equal
    and `body_hash` different.

    The number that matters is the second one. If a repeat carried a body, this
    table would grow with TRAFFIC rather than with edits, which is
    `ledger.call_body` under another name on the readable side of ADR-0018.
    """
    await _signed_in(migrate_engine)
    await _observe(app_sessionmaker, BODY_A, BODY_A, BODY_A, BODY_A, BODY_B)

    async with migrate_engine.begin() as connection:
        total = (await connection.execute(COUNT_SIGHTINGS)).scalar_one()
        with_bodies = (await connection.execute(COUNT_SIGHTINGS_WITH_BODIES)).scalar_one()

    assert total == 5, "every occurrence is counted"
    assert with_bodies == 2, "a repeat of the current body stored one anyway"


async def test_a_call_with_no_system_message_is_not_observed(
    api, migrate_engine, app_sessionmaker
) -> None:
    """Not a failure — there was no prompt in it.

    ADR-0011 makes the revision's body the system message, so a call carrying
    none carries nobody's prompt. Filing it would put a row in the inventory that
    can never become one.
    """
    await _signed_in(migrate_engine)

    draft = ObservationDraft(
        workspace_id=WORKSPACE_A,
        namespace=NAMESPACE,
        call_id="cal_obs_no_system_message_0001",
        consumer_key_id=KEY_ID,
        upstream_model="gpt-4o",
        occurred_at=datetime.now(UTC),
        messages=[{"role": "user", "content": "just a question"}],
    )

    assert await record_observation(app_sessionmaker, draft) is None
    assert await _inbox(api) == []


async def test_a_member_without_the_namespace_sees_nothing(
    api, migrate_engine, app_sessionmaker
) -> None:
    """SR-1 and SR-2. The list is empty and the id is a not-found, not a 403.

    A-116's rule: an observation in a namespace the actor cannot see must be
    byte-identical to one that never existed. A 403 would confirm that a
    product's ungoverned prompts are being collected, and to somebody who has not
    been let into the folder that is the disclosure itself.
    """
    await _signed_in(migrate_engine)
    await _second_member(migrate_engine)
    ids = await _observe(app_sessionmaker, BODY_A)

    assert await _inbox(api, MEMBER_SESSION) == []

    response = await call(
        api, "GET", f"/api/v1/observations/{ids[0]}", headers=_cookie(MEMBER_SESSION)
    )
    assert response.status_code == 404, response.body
    assert response.json()["error"]["code"] == "not_found"


async def test_a_namespace_grant_is_what_opens_it(
    api, migrate_engine, app_sessionmaker
) -> None:
    """ADR-0061 closing SR-2, end to end.

    The same member, the same observation, one `access.namespace_grant` row — and
    the ordinary `may()` union does the rest. No rule of this module's own, and
    no borrowed action.
    """
    await _signed_in(migrate_engine)
    await _second_member(migrate_engine)
    ids = await _observe(app_sessionmaker, BODY_A)

    async with migrate_engine.begin() as connection:
        await connection.execute(
            GRANT_NAMESPACE,
            {
                "workspace_id": WORKSPACE_A,
                "namespace": NAMESPACE,
                "grantee_user_id": MEMBER_ID,
                "granted_by": ADMIN_ID,
            },
        )

    rows = await _inbox(api, MEMBER_SESSION)
    assert [row["observation_id"] for row in rows] == ids

    response = await call(
        api, "GET", f"/api/v1/observations/{ids[0]}", headers=_cookie(MEMBER_SESSION)
    )
    assert response.status_code == 200, response.body
    assert response.json()["current_body"] == BODY_A


async def test_the_proposal_cuts_the_date_out_and_writes_no_prompt(
    api, migrate_engine, app_sessionmaker
) -> None:
    """A-154 proposes and never applies (ADR-0060).

    The route returns a body with slots and a suggested NAME, and it suggests no
    namespace at all — SR-6, because A-021 makes a model name immutable and
    ADR-0061 makes the namespace the access container, so the one convenient
    default here is the one that would follow the prompt for life.
    """
    await _signed_in(migrate_engine)
    ids = await _observe(app_sessionmaker, BODY_A, BODY_B)

    response = await call(
        api, "POST", f"/api/v1/observations/{ids[0]}/proposal", headers=_cookie(ADMIN_SESSION)
    )
    assert response.status_code == 200, response.body
    proposal = response.json()

    assert proposal["variables"] == ["var_1"]
    assert "{{var_1}}" in proposal["body"]
    assert "2026-08-14" not in proposal["body"]
    assert proposal["suggested_name"].startswith("you-are-a-support-agent")
    assert "namespace" not in proposal

    async with migrate_engine.begin() as connection:
        prompts = (
            await connection.execute(text("SELECT count(*) FROM registry.prompt_property"))
        ).scalar_one()
    assert prompts == 0, "the proposal route wrote a prompt; ADR-0060 says it writes nothing"


async def test_redact_keeps_the_counts_and_survives_the_next_call(
    api, migrate_engine, app_sessionmaker
) -> None:
    """SR-4, including the half that is easy to get wrong.

    A product whose key is still pointed at Prope goes on sending the body
    somebody just removed. The write path pins `current_body` and `body_hash` on
    a redacted row and stores no sighting body, so the redaction holds; without
    that the next request would quietly restore the text.
    """
    await _signed_in(migrate_engine)
    ids = await _observe(app_sessionmaker, BODY_A, BODY_B)

    redacted = await call(
        api, "POST", f"/api/v1/observations/{ids[0]}/redacted", headers=_cookie(ADMIN_SESSION)
    )
    assert redacted.status_code == 200, redacted.body
    assert redacted.json()["redacted"] is True
    assert redacted.json()["body_excerpt"] == ""
    assert redacted.json()["sighting_count"] == 2

    await _observe(app_sessionmaker, BODY_A)

    async with migrate_engine.begin() as connection:
        with_bodies = (await connection.execute(COUNT_SIGHTINGS_WITH_BODIES)).scalar_one()

    row = (await _inbox(api))[0]
    assert row["body_excerpt"] == ""
    assert row["sighting_count"] == 3, "a redacted group must go on counting"
    assert with_bodies == 0, "a redacted group stored a body on the next call"


async def test_dismissing_and_then_adopting_leaves_one_state(
    api, migrate_engine, app_sessionmaker
) -> None:
    """Somebody changed their mind, and `status` stays a fact rather than a precedence rule."""
    await _signed_in(migrate_engine)
    ids = await _observe(app_sessionmaker, BODY_A)

    dismissed = await call(
        api,
        "POST",
        f"/api/v1/observations/{ids[0]}/dismissed",
        json_body={"reason": "một lần thử nghiệm"},
        headers=_cookie(ADMIN_SESSION),
    )
    assert dismissed.status_code == 200, dismissed.body
    assert dismissed.json()["status"] == "dismissed"

    adopted = await call(
        api,
        "POST",
        f"/api/v1/observations/{ids[0]}/adopted",
        json_body={"prompt_id": "prm_01J0000000000000000ADOPT"},
        headers=_cookie(ADMIN_SESSION),
    )
    assert adopted.status_code == 200, adopted.body
    assert adopted.json()["status"] == "adopted"
    assert adopted.json()["dismissed_at"] is None
    assert adopted.json()["adopted_prompt_id"] == "prm_01J0000000000000000ADOPT"

    # And the reverse is refused rather than silently applied: a group that is
    # already adopted cannot also be dismissed, and the `WHERE adopted_at IS NULL`
    # in the statement is what makes that true for two people acting at once.
    again = await call(
        api,
        "POST",
        f"/api/v1/observations/{ids[0]}/dismissed",
        json_body={"reason": "đổi ý"},
        headers=_cookie(ADMIN_SESSION),
    )
    assert again.status_code == 409, again.body

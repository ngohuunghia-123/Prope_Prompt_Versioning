"""ADR-0055 — a prompt's call metadata is as private as the prompt, and carries no body.

The endpoint exists because the SPA's call-records screen asks only for metadata,
and ADR-0018 says of metadata *"it is kept indefinitely, it has readers"*. What
that ADR forbids is a **body** read path, and the first test below is what keeps
the two apart in fact rather than in intent.

The rest is BR-01, restated for a surface that did not exist when BR-01 was
written. Every call record names a `prompt_id`, so a workspace-wide list would be
an enumeration oracle for private prompts — which is why there is no such list and
why this one refuses in `_visible_prompt`'s not-found shape, byte-identical to the
answer for an id that never existed.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.prompt_registry.schemas import CallRecordRead
from tests.access_control import (
    MEMBER_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, registry_api, seed_prompt, seed_revision
from tests.unit import WORKSPACE_A

OWNER_SESSION = "ses_callrecords_owner00000001"
COLLEAGUE_SESSION = "ses_callrecords_colleague0001"

#: A `prm_` id with the right shape that no row carries. The control: whatever the
#: API says about this is what it must also say about a prompt the actor may not
#: see.
NONEXISTENT = "prm_01J000000000000000MISSING"

CALL_ONE = "cal_01J00000000000000000CALL1"
CALL_TWO = "cal_01J00000000000000000CALL2"

BODY_TEXT = "the customer asked about a refund and here is what the model said back"

INSERT_CALL_RECORD = text(
    """
    INSERT INTO ledger.call_record (
        call_id, workspace_id, source, prompt_id, version_id, revision_number,
        outcome, pinned, fallback, streaming,
        input_tokens, output_tokens, usage_status,
        cost, currency, price_row_id, cost_status, created_at
    ) VALUES (
        :call_id, :workspace_id, 'gateway', :prompt_id, :version_id, 1,
        'ok', false, false, false,
        120, 340, 'reported',
        NULL, NULL, NULL, 'unpriced', :created_at
    )
    """
)

#: `expires_at` is NOT NULL because a body is write-then-delete: the retention
#: sweep reads this column, and a row without one would survive forever — which is
#: the state `LedgerRetentionOverdue` exists to catch.
INSERT_CALL_BODY = text(
    """
    INSERT INTO ledger.call_body (
        call_id, workspace_id, request_body, response_body, created_at, expires_at
    ) VALUES (
        :call_id, :workspace_id, :request_body, :response_body,
        CAST(:created_at AS timestamptz),
        CAST(:created_at AS timestamptz) + interval '30 days'
    )
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={OWNER_SESSION}"}


def _colleague() -> dict[str, str]:
    return {"cookie": f"prope_session={COLLEAGUE_SESSION}"}


async def _a_private_prompt_that_has_served_traffic(migrate_engine, *, with_body: bool = False):  # noqa: ANN001, ANN202
    """An owner, a colleague with a membership and no role, and two calls.

    The colleague's shape is `test_private_by_default`'s and is the one BR-01 is
    about: legitimately in the workspace, authenticated, entitled to nothing in
    particular. A colleague holding Viewer would have `prompt.read` workspace-wide,
    which is a different test.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, OWNER_SESSION)

    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, COLLEAGUE_SESSION, user_id=MEMBER_ID)

    await seed_prompt(migrate_engine, title="Refund classifier", access_level="private")
    await seed_revision(migrate_engine)

    async with migrate_engine.begin() as connection:
        for index, call_id in enumerate((CALL_ONE, CALL_TWO)):
            await connection.execute(
                INSERT_CALL_RECORD,
                {
                    "call_id": call_id,
                    "workspace_id": WORKSPACE_A,
                    "prompt_id": PROMPT_ID,
                    "version_id": VERSION_ID,
                    "created_at": datetime(2026, 8, 5, 12, index, tzinfo=UTC),
                },
            )
        if with_body:
            await connection.execute(
                INSERT_CALL_BODY,
                {
                    "call_id": CALL_ONE,
                    "workspace_id": WORKSPACE_A,
                    "request_body": BODY_TEXT,
                    "response_body": BODY_TEXT,
                    "created_at": datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
                },
            )


async def test_the_read_returns_metadata_and_no_stored_body(api, migrate_engine) -> None:
    """ADR-0018's line, held. A body exists for one of these calls and does not appear.

    This is the assertion that keeps ADR-0055 from being a quiet reversal of
    ADR-0018. The body is **written** for `CALL_ONE`, so a join that leaked one
    would have something to leak — a version of this test without the insert would
    pass against an endpoint that returned bodies whenever they happened to exist.
    """
    await _a_private_prompt_that_has_served_traffic(migrate_engine, with_body=True)

    response = await call(
        api, "GET", f"/api/v1/prompts/{PROMPT_ID}/call-records", headers=_owner()
    )

    assert response.status_code == 200, response.body
    assert BODY_TEXT not in response.body.decode()
    assert "request_body" not in response.body.decode()
    assert "response_body" not in response.body.decode()

    # And the same claim about the type rather than about one response, so an
    # endpoint that returned a body only on some branch still fails.
    fields = set(CallRecordRead.model_fields)
    assert not [name for name in fields if "body" in name.lower()], fields


async def test_the_read_is_newest_first_and_names_the_consuming_integration(
    api, migrate_engine
) -> None:
    """The positive control. Every refusal below is vacuous without it."""
    await _a_private_prompt_that_has_served_traffic(migrate_engine)

    response = await call(
        api, "GET", f"/api/v1/prompts/{PROMPT_ID}/call-records", headers=_owner()
    )

    assert response.status_code == 200, response.body
    records = response.json()
    assert [record["call_id"] for record in records] == [CALL_TWO, CALL_ONE]
    assert records[0]["version_id"] == VERSION_ID
    assert records[0]["input_tokens"] == 120

    # `actor_id` is metadata and is deliberately not in the read: it names the
    # person who made a call, which is a fact about somebody's working day rather
    # than about the prompt.
    assert "actor_id" not in records[0]


async def test_a_colleague_cannot_read_a_private_prompts_traffic(api, migrate_engine) -> None:
    """BR-01, on a surface it was not written for.

    Byte equality against the nonexistent-id control rather than two separate
    `== 404` checks — two not-founds with different bodies is exactly the oracle
    this closes. And the refusal lands *before* any record is read, so the answer
    cannot vary with how much traffic the prompt has had.
    """
    await _a_private_prompt_that_has_served_traffic(migrate_engine)

    refused = await call(
        api, "GET", f"/api/v1/prompts/{PROMPT_ID}/call-records", headers=_colleague()
    )
    control = await call(
        api, "GET", f"/api/v1/prompts/{NONEXISTENT}/call-records", headers=_colleague()
    )

    assert refused.status_code == control.status_code == 404
    assert _without_request_id(refused) == _without_request_id(control)


async def test_the_read_declares_a_session(api, migrate_engine) -> None:
    """No cookie, no records. It is not one of the two unauthenticated routes."""
    await _a_private_prompt_that_has_served_traffic(migrate_engine)

    response = await call(api, "GET", f"/api/v1/prompts/{PROMPT_ID}/call-records")

    assert response.status_code == 401


def _without_request_id(response) -> dict:  # noqa: ANN001
    payload = response.json()
    error = {key: value for key, value in payload["error"].items() if key != "request_id"}
    return {"error": error}

"""AC-2 — the author approves their own revision, and it is a FACT rather than an error.

ADR-0010 overturned the agent's first answer here, and the distinction is the
whole test: eligibility is a permission question and nothing else. A workspace
that wants author-approver separation expresses it by not granting ``approve`` to
authors — which is the second half below, where the same call from an actor
holding only ``revision.submit`` is refused by access-control rather than by a
rule in this module.

``self_approved`` is STORED rather than derived, for ``evidence_digest``'s
reason: it fixes what was true at decision time, and the author field lives in
another module. Nothing alerts on it. The counter exists so the ratio is
measurable, because the failure mode worth watching — *a workspace grants approve
to everyone and the approval step stops being a second pair of eyes* — is a
number rather than an event.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, seed_prompt, seed_revision
from tests.release_control import (
    ADMIN_ID,
    passing_summary,
    read_approvals,
    release_api,
    seed_actor,
    stub_summary,
)

SESSION_ID = "ses_release_self_approval"

HISTORY_ACTORS = text(
    """
    SELECT actor_id
    FROM   history.history_event
    WHERE  scope_prompt_id = :prompt_id AND action = 'revision_approved'
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with release_api(app_sessionmaker) as application:
        yield application


def _self_approvals() -> float:
    return REGISTRY.get_sample_value("prope_release_self_approval_total") or 0.0


async def _an_author_who_may_also_approve(migrate_engine: AsyncEngine) -> None:
    await seed_actor(migrate_engine, SESSION_ID, roles=("Owner", "Reviewer"))
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, author_id=ADMIN_ID)


async def _submit_and_approve(api, monkeypatch) -> object:  # noqa: ANN001
    await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/submit",
        headers={"cookie": f"prope_session={SESSION_ID}"},
    )
    with stub_summary(monkeypatch, passing_summary(PROMPT_ID, VERSION_ID)):
        return await call(
            api,
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/revisions/{VERSION_ID}/approve",
            json_body={"comment": "I wrote it and I stand behind it"},
            headers={"cookie": f"prope_session={SESSION_ID}"},
        )


async def test_the_author_may_approve_and_the_row_says_so(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    await _an_author_who_may_also_approve(migrate_engine)

    before = _self_approvals()
    approved = await _submit_and_approve(api, monkeypatch)

    assert approved.status_code == 201, approved.body
    assert approved.json()["self_approved"] is True

    approvals = await read_approvals(migrate_engine)
    assert len(approvals) == 1
    assert approvals[0]["self_approved"] is True
    assert approvals[0]["reviewer_id"] == ADMIN_ID

    assert _self_approvals() == before + 1


async def test_the_history_event_carries_the_same_actor(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The trail attributes the decision to the person who made it.

    ``self_approved`` itself is deliberately NOT in the event's details:
    ``revision_approved`` is registered with an empty ``detail_keys`` allow-list,
    and the fact is on the approval row where the Success-metric SQL can join to
    it. What the event carries is who acted, which is what a trail is for.
    """
    await _an_author_who_may_also_approve(migrate_engine)
    await _submit_and_approve(api, monkeypatch)

    async with migrate_engine.begin() as connection:
        actors = (
            await connection.execute(HISTORY_ACTORS, {"prompt_id": PROMPT_ID})
        ).scalars().all()

    assert list(actors) == [ADMIN_ID]


async def test_an_author_holding_only_edit_is_refused_by_access_control(
    api, migrate_engine: AsyncEngine, monkeypatch
) -> None:
    """The same call, the same author, one role fewer.

    This is the pair that makes the first test mean something. Without it,
    "self-approval succeeds" would be indistinguishable from "this module never
    checks anything".
    """
    await seed_actor(migrate_engine, SESSION_ID, roles=("Owner",))
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, author_id=ADMIN_ID)

    refused = await _submit_and_approve(api, monkeypatch)

    assert refused.status_code == 403, refused.body
    assert refused.code == "permission_denied"
    assert refused.json()["error"]["details"]["permission"] == "revision.approve"
    assert await read_approvals(migrate_engine) == []

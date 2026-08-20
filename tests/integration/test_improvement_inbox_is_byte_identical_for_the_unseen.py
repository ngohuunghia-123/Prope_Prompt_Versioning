"""AC-6 / SR-7 — the inbox omits a prompt the reader may not see, IDENTICALLY.

**Not merely "omits it" — omits it byte-for-byte the way a healthy workspace
answers.** Prompts are private by default and that privacy is enforced as
not-found, never forbidden (BR-01). A queue is the easiest place in the product
to lose that: a total that counts what it will not show, a *2 findings hidden*
note, or a severity tally computed before the filter would each disclose the
existence of a prompt somebody deliberately kept private — and would do it on a
screen designed to be glanced at.

**The disclosure would be about the interesting prompts specifically.** An inbox
that leaked counts would not leak the existence of every private prompt; it would
leak the existence of the private prompts that are currently misbehaving, which
is strictly worse.

**The route authorises prompt by prompt and the shape is ADR-0020's.** Permission
is a local decision with the subject passed in: the caller reads the prompt row
and hands `owner_id` and `access_level` to `may()`. A single SQL predicate
joining `registry.prompt_property` would have been faster and is the cross-schema
read ADR-0055 refuses and this module's lock forbids by name — so the loop is not
a naive implementation, it is the one the architecture allows.

The assertion is on the serialised body, not on the parsed one. A test comparing
dictionaries would pass against a response that differed only in key order or in
a field whose value happened to be zero — and *happened to be zero* is exactly
the kind of accident this property cannot rely on.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.prompt_improvement import repository
from prope.prompt_improvement.domain import Anomaly, DetectorId
from tests.access_control import MEMBER_ID, seed_grant, seed_member, seed_session, seed_user
from tests.evaluation import PROMPT_ID, WORKSPACE_A, day, seed_bound_revision, seed_owner
from tests.integration._asgi import call
from tests.prompt_improvement import improvement_api
from tests.prompt_registry import approve, release, seed_prompt

OWNER_SESSION = "ses_improvement_inbox_000001"

MEMBER_SESSION = "ses_improvement_inbox_000002"

VERSION_ID = "rev_01J000000000000000INBOX1"

#: A second prompt nobody has a finding on, so the "empty" baseline is a real
#: workspace with real prompts rather than an empty database.
QUIET_PROMPT = "prm_01J00000000000000000QUIET"

QUIET_VERSION = "rev_01J000000000000000QUIET1"

BODY = "<system>Bạn là trợ lý nội bộ của ACME.</system>"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    yield from improvement_api(app_sessionmaker)


@pytest.fixture
async def a_private_prompt_with_a_finding(
    migrate_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """One private prompt with an open warning, and a colleague who cannot see it.

    **The colleague holds a MEMBERSHIP and no role binding**, which is the shape
    BR-01 is about: somebody legitimately in the workspace, authenticated, and
    entitled to nothing in particular. A colleague with the Viewer role would
    hold ``prompt.read`` workspace-wide and ``visible_subject_filter`` would
    answer ``all`` — in this product a Viewer sees every prompt there is, so
    seeding one here would have made this file assert nothing.
    """
    await seed_owner(migrate_engine, OWNER_SESSION)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(
        migrate_engine, version_id=VERSION_ID, body=BODY, status="Approved"
    )
    await approve(migrate_engine, VERSION_ID)
    await release(migrate_engine, PROMPT_ID, VERSION_ID)

    await seed_prompt(
        migrate_engine, QUIET_PROMPT, access_level="workspace", name="quiet-classifier"
    )
    await seed_bound_revision(
        migrate_engine,
        version_id=QUIET_VERSION,
        prompt_id=QUIET_PROMPT,
        body=BODY,
        status="Approved",
    )
    await approve(migrate_engine, QUIET_VERSION)
    await release(migrate_engine, QUIET_PROMPT, QUIET_VERSION)

    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, MEMBER_SESSION, user_id=MEMBER_ID)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await repository.open_or_bump_finding(
            db,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            anomaly=Anomaly(
                detector_id=DetectorId.FALLBACK_RISING,
                params={"share": 0.3, "prior_share": 0.01},
            ),
            evidence_line="Một phần ba câu trả lời đang rơi về câu trả lời dự phòng.",
            now=day(3),
        )


async def _inbox(api: Any, session_id: str) -> Any:
    return await call(
        api,
        "GET",
        "/api/v1/improvement/findings",
        headers={"cookie": f"prope_session={session_id}"},
    )


async def test_the_owner_sees_the_finding(
    api: Any, a_private_prompt_with_a_finding: None
) -> None:
    """The positive case, so every assertion below is about a filter and not a bug.

    Without this, an inbox that returned nothing to anybody would satisfy the
    byte-identity claim perfectly and would be the implementation this file
    exists to reject.
    """
    response = await _inbox(api, OWNER_SESSION)

    assert response.status_code == 200, response.body
    body = response.json()
    assert body["total"] == 1
    assert body["warning_count"] == 1
    assert body["findings"][0]["detector_id"] == "fallback_rising"
    assert body["findings"][0]["prompt_id"] == PROMPT_ID


async def test_a_reader_who_cannot_see_the_prompt_gets_the_empty_workspace_answer(
    api: Any, a_private_prompt_with_a_finding: None
) -> None:
    """**SR-7, on the bytes.**

    The colleague is authenticated, is a member of the workspace, and the route
    answers them ``200``. What they cannot see is this prompt — private, and not
    theirs — so the finding contributes nothing: no row, no count, no total, and
    no difference from the response a workspace with nothing wrong would send.
    """
    seen = await _inbox(api, OWNER_SESSION)
    unseen = await _inbox(api, MEMBER_SESSION)

    assert seen.status_code == unseen.status_code == 200
    assert unseen.json() == {
        "findings": [],
        "total": 0,
        "warning_count": 0,
        "advice_count": 0,
    }
    assert seen.body != unseen.body, "the fixture is not producing a visible finding"


async def test_the_bytes_match_a_workspace_where_nothing_is_wrong(
    api: Any, migrate_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """The comparison SR-7 actually names, made against a second real workspace.

    The claim is not *the member sees an empty list* — that is only half of it. It
    is that the response is INDISTINGUISHABLE from the one a workspace with no
    findings sends, so a reader cannot infer from a totals row, a key order or a
    field's presence that something is being withheld.
    """
    await seed_owner(migrate_engine, OWNER_SESSION)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(
        migrate_engine, version_id=VERSION_ID, body=BODY, status="Approved"
    )
    await approve(migrate_engine, VERSION_ID)
    await release(migrate_engine, PROMPT_ID, VERSION_ID)

    healthy = await _inbox(api, OWNER_SESSION)

    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, MEMBER_SESSION, user_id=MEMBER_ID)
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await repository.open_or_bump_finding(
            db,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            anomaly=Anomaly(detector_id=DetectorId.FALLBACK_RISING, params={"share": 0.3}),
            evidence_line=None,
            now=day(3),
        )

    withheld = await _inbox(api, MEMBER_SESSION)

    assert healthy.body == withheld.body


async def test_a_grant_makes_the_same_finding_appear(
    api: Any, migrate_engine: AsyncEngine, a_private_prompt_with_a_finding: None
) -> None:
    """The filter is about VISIBILITY and not about who is asking.

    A route that always returned nothing to a non-owner would pass every
    assertion above. A direct grant on the one prompt changes the answer — the
    colleague still holds no role — which is what proves the omission was a
    permission decision rather than a hard-coded ownership check, and that it
    takes effect on the very next request.
    """
    before = await _inbox(api, MEMBER_SESSION)
    assert before.json()["total"] == 0

    await seed_grant(migrate_engine, "viewer", prompt_id=PROMPT_ID, grantee_user_id=MEMBER_ID)

    after = await _inbox(api, MEMBER_SESSION)
    assert after.json()["total"] == 1
    assert after.json()["findings"][0]["prompt_id"] == PROMPT_ID


async def test_the_per_prompt_tab_answers_not_found_rather_than_forbidden(
    api: Any, a_private_prompt_with_a_finding: None
) -> None:
    """A-116 at the single-prompt route, which the list route cannot express.

    The list omits; this refuses, and the refusal has to be not-found. Forbidden
    would confirm the prompt exists — and the reader would have learned it from a
    findings endpoint, which is a door nobody classified as a read (BR-01).
    """
    response = await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/findings",
        headers={"cookie": f"prope_session={MEMBER_SESSION}"},
    )

    assert response.status_code == 404, response.body

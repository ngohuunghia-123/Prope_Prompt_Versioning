"""AC-2 — the review screen's diff, through the route, at A-050's cap.

Two claims, and the second is the one with a number attached:

* a **line-level** diff of the body plus a **field-level** comparison of
  provider, upstream model, parameters and fallback answer;
* rendered in **under 300 ms with both bodies at 32 KiB**.

The timing assertion is what pays for ``autojunk=False``. Disabling the
heuristic removes ``difflib``'s quadratic-case guard, and the lock says in as
many words that *"the cost is under test rather than assumed"* — this is the
test. It measures the route rather than the function, so the number covers the
database reads and the JSON serialisation of a diff over two 32 KiB bodies, not
only the matcher.

**The body it measures is the one that broke the budget.** Two 32 KiB bodies
made of unrelated text are cheap, because nothing matches anything. The
expensive shape is a long list of near-identical lines with one line changed in
the middle — which is a prompt with many examples, and therefore most 32 KiB
prompts. Measured before the prefix/suffix trim in ``diff.py``, that shape took
1.2 s; a test that used disjoint bodies would have passed at 3 ms and said
nothing.

**The timed request runs against a POOLED engine, and that is a correction
rather than a convenience.** ``tests/conftest.py`` builds every shared engine
with ``NullPool``, for a stated reason that has nothing to do with performance:
an asyncpg connection is bound to the event loop that opened it, and the shared
fixtures are session-scoped across many loops. The cost is that **every**
``workspace_transaction`` opens a fresh connection, and a fresh asyncpg
connection performs a SCRAM-SHA-256 handshake — 4,096 pure-Python HMAC rounds,
profiled here at ~300 ms of the ~440 ms this request took. That is the rig's
authentication, not A-015's diff, and the deployed process pays it once per
pooled connection rather than once per request. Measuring the budget through
``NullPool`` would be measuring something no user experiences, so this one test
builds an engine with the default pool inside its own loop and disposes it.
"""

import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.engine import build_engine, build_sessionmaker
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.conftest import _role_url
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, VERSION_ID, registry_api, seed_prompt, seed_revision

SESSION_ID = "ses_registry_diff_0000000001"

SECOND_VERSION = "rev_01J000000000000000000REV2"

#: A-050's cap, and the condition AC-2 names. Built from many short repeated
#: lines rather than one long one, because that is the shape ``autojunk`` was
#: written for and therefore the shape the guard's removal costs most on.
CAP = 32768

BUDGET_SECONDS = 0.3

_LINE = "- an example about refunds\n"


def _body(changed_line: str | None = None) -> str:
    """A body at the cap: repeated bullets, optionally one of them changed.

    Both halves are needed. Repetition is what makes the matcher expensive, and
    changing exactly one line in the middle is what stops the two sequences being
    trivially unrelated — the case where the matcher finds nothing and returns
    immediately.
    """
    lines = (_LINE * (CAP // len(_LINE)))[:CAP].splitlines()
    if changed_line is not None:
        lines[len(lines) // 2] = changed_line
    return "\n".join(lines)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _reviewer() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _two_revisions(migrate_engine, before: str, after: str, **overrides) -> None:  # noqa: ANN001, ANN003
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, body=before)
    await seed_revision(
        migrate_engine,
        version_id=SECOND_VERSION,
        revision_number=2,
        body=after,
        change_summary="the second",
        **overrides,
    )


async def _diff(api, params: dict | None = None):  # noqa: ANN001, ANN202
    return await call(
        api,
        "GET",
        f"/api/v1/prompts/{PROMPT_ID}/diff",
        params=params or {"from": VERSION_ID, "to": SECOND_VERSION},
        headers=_reviewer(),
    )


async def test_the_response_carries_both_halves(api, migrate_engine) -> None:
    """One response rather than two endpoints, because the screen shows both.

    A client that could fetch the body diff without the field comparison would
    eventually ship a screen showing a text change with no note that the model
    underneath it changed too — which is the gap A-015's *"textual, not
    consequence-language"* already leaves, widened.
    """
    await _two_revisions(
        migrate_engine,
        "one\ntwo\nthree",
        "one\ntwo point five\nthree",
        fallback_answer="We could not answer that.",
    )

    response = await _diff(api)

    assert response.status_code == 200, response.body
    payload = response.json()

    assert payload["prompt_id"] == PROMPT_ID
    assert payload["from_version_id"] == VERSION_ID
    assert payload["to_version_id"] == SECOND_VERSION

    assert [line["op"] for line in payload["lines"]] == [
        "equal",
        "removed",
        "added",
        "equal",
    ]

    changed = [field for field in payload["fields"] if field["changed"]]
    assert [field["field"] for field in changed] == ["fallback_answer"]
    assert changed[0]["after"] == "We could not answer that."


async def test_the_diff_renders_under_the_budget_with_both_bodies_at_the_cap(
    migrate_engine, postgres_container
) -> None:
    """AC-2's number, measured over the route and not over the matcher.

    Warmed first, and the warm-up is doing real work: it fills the pool and pays
    the SCRAM handshake, neither of which the deployed process repeats per
    request.

    The response is checked as well as the clock, because a diff that returned
    the wrong answer quickly would pass a timing assertion on its own.
    """
    await _two_revisions(migrate_engine, _body(), _body("- an example about chargebacks"))

    engine = build_engine(_role_url(postgres_container, "prope_app"))
    try:
        with registry_api(build_sessionmaker(engine)) as pooled:
            warm = await _diff(pooled)
            assert warm.status_code == 200, warm.body

            started = time.perf_counter()
            response = await _diff(pooled)
            elapsed = time.perf_counter() - started
    finally:
        await engine.dispose()

    assert response.status_code == 200
    assert elapsed < BUDGET_SECONDS, f"{elapsed:.3f}s over the {BUDGET_SECONDS}s budget"

    ops = [line["op"] for line in response.json()["lines"]]
    assert ops.count("removed") == 1
    assert ops.count("added") == 1
    assert ops.count("equal") == len(_body().splitlines()) - 1


async def test_a_revision_from_another_prompt_is_refused(api, migrate_engine) -> None:
    """The check that stops the diff being a read path around the permission check.

    Without it, a caller with permission on one prompt could diff two revisions of
    another and read both bodies out of the response — the permission is checked
    against the prompt in the PATH, so the revisions have to belong to it.
    """
    await _two_revisions(migrate_engine, "one", "two")
    await seed_prompt(
        migrate_engine,
        prompt_id="prm_01J0000000000000000OTHER",
        namespace="other",
        name="thing",
    )
    await seed_revision(
        migrate_engine,
        version_id="rev_01J0000000000000000OTHER",
        prompt_id="prm_01J0000000000000000OTHER",
        body="somebody else's text",
    )

    response = await _diff(
        api, {"from": VERSION_ID, "to": "rev_01J0000000000000000OTHER"}
    )

    assert response.status_code == 404
    assert response.code == "not_found"
    assert b"somebody else" not in response.body


async def test_an_unknown_version_is_not_found(api, migrate_engine) -> None:
    await _two_revisions(migrate_engine, "one", "two")

    response = await _diff(api, {"from": VERSION_ID, "to": "rev_01J00000000000000MISSING"})

    assert response.status_code == 404


async def test_the_diff_is_not_stored_anywhere(api, migrate_engine) -> None:
    """A-047: computed on demand, never stored.

    A stored diff would be a THIRD copy of the prompt body, on top of
    ``revision`` and ``search_text`` — and T-017 already shows what the second
    one costs to keep out of a response. Asserted over the schema rather than
    over the code, because a table added later would pass a source check that
    looked for a cache.

    The list is every table in the schema, so a diff cache appearing under any
    name fails here. That also means every table added for an unrelated reason
    has to be added — `folder` at 0016 and `call_annotation` at 0039 both were
    not, and this assertion has been red since. Neither stores a body: a folder
    is a name and a colour, and an annotation is a comment keyed to a call.
    """
    await _two_revisions(migrate_engine, "one", "two")
    await _diff(api)

    async with migrate_engine.begin() as connection:
        tables = (
            await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'registry' "
                    "ORDER BY tablename"
                )
            )
        ).scalars().all()

    assert tables == ["call_annotation", "folder", "prompt_property", "revision"]

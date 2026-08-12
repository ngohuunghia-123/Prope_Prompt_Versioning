"""AC-6 — a run and a case result of a private prompt are absent, not forbidden.

The same rule ``tests/security/test_private_by_default.py`` asserts for prompts,
on the two routes that authorise against a DIFFERENT row than the one in the
path. ``GET /eval-runs/{id}`` has to read the run before it knows which prompt to
ask about, so the run — and, one route further, every case's output text — is in
memory at the moment permission is refused.

Two things must hold and only the first is obvious:

* the refusal is ``404``, byte-identical to the refusal for an id that never
  existed. A ``403`` would confirm that a run exists for a prompt the actor
  cannot see, and a run id is guessable in exactly the way a prompt id is;
* **no output text is returned.** The case results carry the model's answers,
  which are the most sensitive rows this module owns, and they are already loaded
  when the refusal happens.

Asserted as byte equality of the two envelopes rather than as two separate
``== 404`` checks, because two 404s with different bodies is exactly the oracle
this is meant to close.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.access_control import MEMBER_ID, seed_grant, seed_member, seed_session, seed_user
from tests.evaluation import (
    CASE_ID,
    PROMPT_ID,
    RUN_ID,
    SUITE_ID,
    evaluation_api,
    seed_bound_revision,
    seed_case,
    seed_case_result,
    seed_owner,
    seed_run,
    seed_suite,
)
from tests.integration._asgi import call
from tests.prompt_registry import seed_prompt

OWNER_SESSION = "ses_evaluation_private_own01"

COLLEAGUE_SESSION = "ses_evaluation_private_oth01"

#: An ``evr_`` id with the right shape that no row carries. The control for every
#: not-found assertion below: whatever the API says about this is what it must
#: also say about a run the actor may not see.
NONEXISTENT_RUN = "evr_01J000000000000000MISSIN"

NONEXISTENT_SUITE = "evs_01J000000000000000MISSIN"

#: The model's answer. If this string ever appears in a refusal's bytes, the
#: refusal leaked the thing it was refusing.
SECRET_OUTPUT = "the customer's card ends 4242 and the refund was approved"


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with evaluation_api(app_sessionmaker) as application:
        yield application


def _colleague() -> dict[str, str]:
    return {"cookie": f"prope_session={COLLEAGUE_SESSION}"}


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={OWNER_SESSION}"}


async def _a_private_run_and_a_colleague_with_no_role(migrate_engine) -> None:  # noqa: ANN001
    """The colleague holds a MEMBERSHIP and no role binding.

    That is the shape BR-01 is about: somebody legitimately in the workspace,
    authenticated, and entitled to nothing in particular. A colleague with the
    Viewer role would hold ``run.read`` workspace-wide, which is a different
    test — and the one that would silently make this file pass for the wrong
    reason.
    """
    await seed_owner(migrate_engine, OWNER_SESSION)
    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, COLLEAGUE_SESSION, user_id=MEMBER_ID)

    await seed_prompt(migrate_engine, access_level="private")
    await seed_bound_revision(migrate_engine)

    await seed_suite(migrate_engine, case_count=1)
    await seed_case(migrate_engine)
    await seed_run(migrate_engine, status="completed", pass_count=1, finished_at=None)
    await seed_case_result(
        migrate_engine,
        "evcr_01J00000000000000RESULT1",
        output_content=SECRET_OUTPUT,
    )


def _without_request_id(response) -> dict:  # noqa: ANN001
    error = dict(response.json()["error"])
    error.pop("request_id")
    return error


async def test_a_run_read_is_byte_identical_to_a_nonexistent_id(
    api, migrate_engine
) -> None:
    """AC-6's first half. Not two 404s — the SAME 404."""
    await _a_private_run_and_a_colleague_with_no_role(migrate_engine)

    hidden = await call(api, "GET", f"/api/v1/eval-runs/{RUN_ID}", headers=_colleague())
    missing = await call(
        api, "GET", f"/api/v1/eval-runs/{NONEXISTENT_RUN}", headers=_colleague()
    )

    assert hidden.status_code == missing.status_code == 404
    assert _without_request_id(hidden) == _without_request_id(missing)
    assert _without_request_id(hidden)["code"] == "not_found"


async def test_the_case_results_route_returns_no_output_text(api, migrate_engine) -> None:
    """AC-6's second half, and the reason the refusal shape is not enough alone.

    The handler loads the run to resolve its prompt, refuses, and the case
    results are one query further on. A refusal that had been raised after the
    read — or a handler that logged what it was refusing — would put the model's
    answer in this response's bytes.
    """
    await _a_private_run_and_a_colleague_with_no_role(migrate_engine)

    refused = await call(
        api, "GET", f"/api/v1/eval-runs/{RUN_ID}/cases", headers=_colleague()
    )

    assert refused.status_code == 404
    assert SECRET_OUTPUT.encode() not in refused.body

    allowed = await call(api, "GET", f"/api/v1/eval-runs/{RUN_ID}/cases", headers=_owner())
    assert allowed.status_code == 200
    assert allowed.json()[0]["output_content"] == SECRET_OUTPUT


@pytest.mark.parametrize(
    "method,path,body,params",
    [
        ("GET", f"/api/v1/eval-runs/{RUN_ID}", None, None),
        ("GET", f"/api/v1/eval-runs/{RUN_ID}/cases", None, None),
        ("GET", f"/api/v1/eval-suites/{SUITE_ID}", None, None),
        ("PUT", f"/api/v1/eval-suites/{SUITE_ID}", {"output_modality": "text", "cases": []}, None),
        ("GET", f"/api/v1/prompts/{PROMPT_ID}/eval-suites", None, None),
        (
            "POST",
            f"/api/v1/prompts/{PROMPT_ID}/eval-suites",
            {"name": "mine now", "output_modality": "text", "cases": []},
            None,
        ),
        ("GET", f"/api/v1/prompts/{PROMPT_ID}/eval-suites/safety/versions", None, None),
        ("POST", f"/api/v1/prompts/{PROMPT_ID}/eval-runs", {"version_id": "rev_x"}, None),
        (
            "GET",
            f"/api/v1/prompts/{PROMPT_ID}/comparison",
            None,
            {"candidate": "rev_01J000000000000000000REV1"},
        ),
    ],
)
async def test_every_route_refuses_as_not_found(
    api,
    migrate_engine,
    method: str,
    path: str,
    body: dict | None,
    params: dict | None,
) -> None:
    """The rule holds on EVERY route this module mounts, not only the reads.

    A write route is the one somebody adds later without thinking about the
    refusal shape, and a ``PUT`` that answered ``403`` would confirm the suite
    exists just as loudly as a ``GET`` that did. Parametrised so a tenth route is
    one line here rather than a decision nobody revisits.
    """
    await _a_private_run_and_a_colleague_with_no_role(migrate_engine)

    response = await call(
        api, method, path, params=params, json_body=body, headers=_colleague()
    )

    assert response.status_code == 404, response.body
    assert response.code == "not_found"


async def test_a_grant_makes_the_run_visible_on_the_very_next_request(
    api, migrate_engine
) -> None:
    """The control. Without it, a handler that answered 404 to everybody passes.

    ADR-0022 through this module's own reads: there is no cache to wait out, so
    the grant takes effect on the next request and the same id that was absent
    resolves.
    """
    await _a_private_run_and_a_colleague_with_no_role(migrate_engine)

    before = await call(api, "GET", f"/api/v1/eval-runs/{RUN_ID}", headers=_colleague())
    assert before.status_code == 404

    await seed_grant(migrate_engine, "viewer")

    after = await call(api, "GET", f"/api/v1/eval-runs/{RUN_ID}", headers=_colleague())
    assert after.status_code == 200
    assert after.json()["run_id"] == RUN_ID
    assert after.json()["suite_id"] == SUITE_ID


async def test_an_unknown_suite_and_a_hidden_suite_answer_alike(
    api, migrate_engine
) -> None:
    """The suite id is as guessable as the run id, and answers the same way.

    Included separately because ``read_eval_suite`` resolves the prompt through
    the suite row — a second place where the subject of the permission check is
    not the thing in the path, and therefore a second place the shape could
    diverge.
    """
    await _a_private_run_and_a_colleague_with_no_role(migrate_engine)

    hidden = await call(api, "GET", f"/api/v1/eval-suites/{SUITE_ID}", headers=_colleague())
    missing = await call(
        api, "GET", f"/api/v1/eval-suites/{NONEXISTENT_SUITE}", headers=_colleague()
    )

    assert hidden.status_code == missing.status_code == 404
    assert _without_request_id(hidden) == _without_request_id(missing)
    assert CASE_ID.encode() not in hidden.body

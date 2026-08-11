"""AC-11. Take the database away mid-request; every caller refuses and none allows.

**The mechanism is the absence of an `except`.** `permissions.may()` has no `try`
and neither does any caller (A-142 §2, INT-001), so an unavailable oracle
propagates and becomes a `5xx`. That is the whole design: a caller that wrapped
`may()` in a handler would have had to choose a default, and the tempting default
is the one that keeps the screen working.

This asserts the property in both directions. The refusal is checked — a `5xx`,
never a `200` and never a `403` that reads like a policy decision — and so is the
**absence of an allow**: no log line and no `check_total{result="allow"}`
increment on the failed path.

`CALLERS` is a module-level list phases 10–24 extend rather than rewrite. Today it
holds call-ledger's five routes and access-control's own; the rest is owed and
named below rather than silently uncovered.
"""

import pytest
from fastapi import FastAPI
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from prope.access_control.actions import Action
from prope.access_control.api import router as access_control_router
from prope.access_control.domain import AccessLevel, Actor, ActorType, Subject, SubjectType
from prope.access_control.permissions import may, may_resolve, visible_subject_filter
from prope.access_control.seams import authenticate_api_key, authenticate_session
from prope.call_ledger.api import router as call_ledger_router
from prope.db.engine import build_engine
from prope.db.session import workspace_transaction
from prope.errors import install_error_envelope
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    KEY_ID,
    PROMPT_ID,
    WORKSPACE_A,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call

SESSION_ID = "ses_fail_closed_0000000000001"

BACKEND_PID = text("SELECT pg_backend_pid()")

#: Every route in the product that reaches a database, as `(method, path)`.
#:
#: **Extend this, do not rewrite it.** Phase 10 adds prompt-registry's, phase 14
#: release-control's, phase 19 the gateway's. The list is what makes AC-11 a
#: product-wide claim rather than a per-module one, and a phase that added routes
#: without adding lines here would leave the claim quietly narrower than it reads.
CALLERS = (
    ("GET", "/api/v1/prices"),
    ("GET", "/api/v1/prices/unpriced"),
    ("GET", f"/api/v1/workspaces/{WORKSPACE_A}/members"),
    ("GET", f"/api/v1/workspaces/{WORKSPACE_A}/keys"),
    ("GET", "/api/v1/permissions"),
)

#: Phases that own routes not yet in `CALLERS`. Read, not executed.
OWED = {"prompt-registry": 10, "evaluation": 16, "release-control": 14, "gateway": 19}


def _actor() -> Actor:
    return Actor(type=ActorType.USER, id=ADMIN_ID, workspace_id=WORKSPACE_A)


def _subject() -> Subject:
    return Subject(
        type=SubjectType.PROMPT,
        id=PROMPT_ID,
        workspace_id=WORKSPACE_A,
        owner_id=None,
        access_level=AccessLevel.PRIVATE,
    )


def _allow_count() -> float:
    total = 0.0
    for action in Action:
        sample = REGISTRY.get_sample_value(
            "prope_access_control_check_total",
            {"action": action.value, "result": "allow"},
        )
        total += sample or 0.0
    return total


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    """Both routers, mounted as `prope.app` mounts them."""
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(call_ledger_router)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


@pytest.fixture
async def superuser_engine(postgres_container):
    """`pg_terminate_backend` needs a role that can signal another backend, and
    `prope_migrate` is not one — it holds no `pg_signal_backend` membership."""
    engine = build_engine(postgres_container.get_connection_url(), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def signed_in(migrate_engine) -> dict[str, str]:
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, SESSION_ID)
    return {"cookie": f"prope_session={SESSION_ID}"}


class _Unavailable:
    """A sessionmaker whose every session raises on first use.

    Blunter than terminating a backend and it reaches further: the failure lands
    wherever the caller first touches the database, including inside
    `require_session`, which is the earliest point any request can fail. A killed
    backend can only be aimed at a transaction that has already opened.
    """

    def __call__(self, *_args: object, **_kwargs: object) -> "_Unavailable":
        return self

    async def __aenter__(self) -> "_Unavailable":
        raise ConnectionError("the database is gone")

    async def __aexit__(self, *_args: object) -> bool:
        return False


async def test_the_callers_answer_normally_first(api, signed_in) -> None:
    """The positive control. Every refusal below is vacuous without it."""
    for method, path in CALLERS:
        response = await call(api, method, path, headers=signed_in)
        assert response.status_code == 200, (path, response.body)


@pytest.mark.parametrize(("method", "path"), CALLERS)
async def test_every_caller_refuses_when_the_database_is_gone(
    api, signed_in, method: str, path: str
) -> None:
    """A `5xx` and never a `200`. The absence of an `except` is what produces it."""
    before = _allow_count()
    api.state.sessionmaker = _Unavailable()

    with pytest.raises(ConnectionError):
        await call(api, method, path, headers=signed_in)

    assert _allow_count() == before, f"{path} counted an allow on a failed check"


async def _kill(superuser_engine, db) -> None:
    """Terminate the backend this session is holding, from outside it."""
    pid = (await db.execute(BACKEND_PID)).scalar_one()
    async with superuser_engine.begin() as killer:
        await killer.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})


async def test_may_raises_rather_than_returning_a_default(
    migrate_engine, superuser_engine, app_sessionmaker
) -> None:
    """`may()` has no `try`, so an unanswerable oracle is never a `False` either.

    A `False` would be safe *and* wrong: it is indistinguishable from a policy
    deny, so an outage would render as everybody's permissions having been
    revoked — and it would be counted on the deny series
    `AccessControlDenyRateSpike` watches, which is the alert that would then be
    firing about the wrong thing.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)

    before = _allow_count()
    with pytest.raises(Exception) as raised:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await _kill(superuser_engine, db)
            await may(db, _actor(), Action.PROMPT_READ, _subject())

    assert not isinstance(raised.value, AssertionError)
    assert _allow_count() == before


async def test_the_visibility_seam_raises_rather_than_returning_all(
    migrate_engine, superuser_engine, app_sessionmaker
) -> None:
    """The dangerous default here is `all`, not `none`.

    A caller handed `VisibleFilter.all()` runs its list query unfiltered, which is
    every prompt in the workspace on one screen. Raising is the only answer that
    cannot become that.
    """
    await seed_workspace(migrate_engine)

    with pytest.raises(Exception) as raised:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await _kill(superuser_engine, db)
            await visible_subject_filter(db, _actor(), SubjectType.PROMPT)

    assert not isinstance(raised.value, AssertionError)


async def test_may_resolve_raises_rather_than_allowing(
    migrate_engine, superuser_engine, app_sessionmaker
) -> None:
    """A gateway call refused loudly beats one served against an unknown scope."""
    await seed_workspace(migrate_engine)

    with pytest.raises(Exception) as raised:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await _kill(superuser_engine, db)
            await may_resolve(db, KEY_ID, "prope/greeting")

    assert not isinstance(raised.value, AssertionError)


async def test_the_two_bootstrap_seams_raise_rather_than_admitting(app_sessionmaker) -> None:
    """INT-003 and INT-005. A raise is a `5xx`; the gateway does not fall back.

    It does not serve a cached principal and does not admit the request — there is
    no cache to serve from, which is A-114 doing this job as well as its own.
    """
    unavailable = _Unavailable()

    with pytest.raises(ConnectionError):
        await authenticate_session(unavailable, "ses_anything-at-all")

    with pytest.raises(ConnectionError):
        await authenticate_api_key(unavailable, f"prope_{KEY_ID}_a-secret")


def test_the_callers_owed_by_later_phases_are_named() -> None:
    """AC-11 is a product-wide claim and today it covers two modules.

    Stated so the gap is read rather than inferred from a list that happens to be
    short.
    """
    assert all(phase > 9 for phase in OWED.values())
    assert len(CALLERS) == 5

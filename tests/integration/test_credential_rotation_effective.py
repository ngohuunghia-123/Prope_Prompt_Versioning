"""AC-8 — a rotation is effective everywhere within one TTL, and it leaves no readable trail.

Two claims, and the second is the one a rotation is *for*:

* the record is **replaced in place**, so no readable history of a secret
  accumulates (A-025, A-092); and
* the history event records that a rotation happened, by whom and when, and
  contains no part of either credential (A-046, ADR-0024).
"""

import socket

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.db.session import workspace_transaction
from prope.errors import install_error_envelope
from prope.provider_access import credentials
from prope.provider_access.api import router as provider_access_router
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.provider_access import (
    CONFIG_ID,
    SECRET,
    _stub,
    seed_credential,
    seed_provider_config,
)
from tests.unit import WORKSPACE_A

ADMIN_SESSION = "ses_provider_rotate_000000001"

NEW_SECRET = "sk-live-111111111111beef"

COUNT_CREDENTIALS = text("SELECT count(*) FROM provider.credential")

READ_CREDENTIAL = text(
    "SELECT id, ciphertext, last_four, rotated_at FROM provider.credential "
    "WHERE provider_config_id = :id"
)

READ_ROTATION_EVENTS = text(
    "SELECT actor_id, target_id, details::text, reason FROM history.history_event "
    "WHERE action = 'credential_rotated' ORDER BY seq"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(provider_access_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


#: The one name this fixture may answer for. Read from the stub rather than
#: retyped, so a stub that moved host would break loudly here instead of
#: silently falling through to the real resolver.
PROVIDER_HOST = "provider.example"


@pytest.fixture(autouse=True)
def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer for the provider's hostname only, and defer everything else.

    The stub answers below the transport, so the SSRF guard still has to resolve
    a name — and ``provider.example`` does not exist. A public answer here is
    what keeps the guard in the path rather than switched off.

    **Only that one name**, because this is a process-wide patch. Answering
    ``93.184.216.34`` for every host also answers it for the ``localhost`` this
    test's own Postgres container listens on, and ``migrate_engine`` uses
    ``NullPool`` — so every seeding call opens a fresh connection, resolves
    through here, and dials an address nobody is listening on. The symptom is a
    ``WinError 121`` semaphore timeout inside ``seed_workspace``, which reads as
    a database problem and is a DNS one.
    """
    real = socket.getaddrinfo

    def getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        if host == PROVIDER_HOST:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_stub.PUBLIC_ADDRESS, port))]
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


def _provider():  # noqa: ANN202
    return _stub.route(
        models=lambda request: httpx.Response(200, json=_stub.model_list()),
        completions=lambda request: httpx.Response(200, json=_stub.completion()),
    )


async def _configured(migrate_engine) -> dict[str, str]:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, ADMIN_SESSION)
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)
    return {"cookie": f"prope_session={ADMIN_SESSION}"}


async def test_a_rotation_replaces_the_row_rather_than_appending_a_second(
    api, migrate_engine, app_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await _configured(migrate_engine)

    with _stub.stub_provider(monkeypatch, _provider()):
        response = await call(
            api,
            "POST",
            f"/api/v1/providers/{CONFIG_ID}/credential",
            json_body={"credential": NEW_SECRET},
            headers=headers,
        )

    assert response.status_code == 200, response.body
    assert response.json()["credential_last_four"] == NEW_SECRET[-4:]

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_CREDENTIALS) == 1
        row = (await db.execute(READ_CREDENTIAL, {"id": CONFIG_ID})).one()

    assert row.last_four == NEW_SECRET[-4:]
    assert row.rotated_at is not None


async def test_the_next_dispatch_uses_the_new_credential_with_no_restart(
    api, migrate_engine, app_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache is the mechanism and the rotation invalidates the one entry it
    owns; every other process reaches the same state when its own 60 s TTL
    expires, which is the whole of A-092 (and ADR-0012's shape)."""
    headers = await _configured(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await credentials.resolve_secret(db, CONFIG_ID) == SECRET

    assert credentials.cached_secret(CONFIG_ID) == SECRET

    with _stub.stub_provider(monkeypatch, _provider()):
        await call(
            api,
            "POST",
            f"/api/v1/providers/{CONFIG_ID}/credential",
            json_body={"credential": NEW_SECRET},
            headers=headers,
        )

    assert credentials.cached_secret(CONFIG_ID) is None

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await credentials.resolve_secret(db, CONFIG_ID) == NEW_SECRET


async def test_a_cached_credential_expires_on_its_own_after_the_ttl(app_sessionmaker) -> None:
    """Nothing invalidates a cache in another process — the TTL expiring
    independently is the entire mechanism, so the arithmetic is asserted."""
    credentials._cache["prv_01TTL"] = ("sk-old", 100.0)

    assert credentials.cached_secret("prv_01TTL", now=99.0) == "sk-old"
    assert credentials.cached_secret("prv_01TTL", now=100.0) is None
    assert credentials.CACHE_TTL_SECONDS == 60.0


async def test_the_rotation_event_names_the_actor_and_carries_no_credential(
    api, migrate_engine, app_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await _configured(migrate_engine)

    with _stub.stub_provider(monkeypatch, _provider()):
        await call(
            api,
            "POST",
            f"/api/v1/providers/{CONFIG_ID}/credential",
            json_body={"credential": NEW_SECRET},
            headers=headers,
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        events = (await db.execute(READ_ROTATION_EVENTS)).all()

    assert len(events) == 1
    actor_id, target_id, details, reason = events[0]

    assert actor_id == ADMIN_ID
    assert target_id == CONFIG_ID
    assert details == "{}"
    assert reason is None
    assert SECRET not in details
    assert NEW_SECRET not in details
    assert NEW_SECRET[-4:] not in details


async def test_a_rotation_whose_probe_fails_changes_nothing(
    api, migrate_engine, app_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The new credential is probed before it becomes active (A-090), so a
    mistyped key cannot take a working configuration out of service."""
    headers = await _configured(migrate_engine)

    with _stub.stub_provider(monkeypatch, _stub.answers(401, {"error": {"message": "no"}})):
        response = await call(
            api,
            "POST",
            f"/api/v1/providers/{CONFIG_ID}/credential",
            json_body={"credential": NEW_SECRET},
            headers=headers,
        )

    assert response.status_code == 422

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await credentials.resolve_secret(db, CONFIG_ID) == SECRET
        row = (await db.execute(READ_CREDENTIAL, {"id": CONFIG_ID})).one()

    assert row.last_four == SECRET[-4:]
    assert row.rotated_at is None

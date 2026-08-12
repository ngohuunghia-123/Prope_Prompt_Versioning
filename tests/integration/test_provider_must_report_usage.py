"""AC-3 — a provider that returns no usage object cannot be registered (A-030, A-090).

This is ADR-0013's closing obligation, discharged where the ADR said it belongs:
*"a provider that ignores include_usage is a provider-access admission question,
not a gateway workaround."* The probe is where admission is decided, so a
near-compatible endpoint fails on the dashboard rather than in production.
"""

import socket

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.db.session import workspace_transaction
from prope.errors import ErrorCode, install_error_envelope
from prope.provider_access.api import router as provider_access_router
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.provider_access import _stub
from tests.unit import WORKSPACE_A

ADMIN_SESSION = "ses_provider_admin_0000000001"

COUNT_CONFIGS = text("SELECT count(*) FROM provider.provider_config")
COUNT_CREDENTIALS = text("SELECT count(*) FROM provider.credential")
COUNT_EVENTS = text(
    "SELECT count(*) FROM history.history_event WHERE action = 'provider_configured'"
)

BODY = {
    "display_name": "Acme OpenAI",
    "base_url": "https://provider.example/v1",
    "credential": "sk-live-000000000000cafe",
}

#: The whole of the difference between an admitted provider and a refused one.
COMPLETION_WITHOUT_USAGE = {
    "id": "cmpl-1",
    "object": "chat.completion",
    "created": 1_760_000_000,
    "model": "gpt-4o-mini",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}
    ],
}


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


#: The one name this fixture may answer for.
PROVIDER_HOST = "provider.example"


@pytest.fixture(autouse=True)
def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stub answers below the transport, so the guard still has to resolve
    a name — and `provider.example` does not exist. A public answer here is what
    keeps the SSRF guard in the path rather than switched off.

    **Only that one name.** This is a process-wide patch, and answering
    ``93.184.216.34`` for every host also answers it for the ``localhost`` this
    test's own Postgres container listens on. ``migrate_engine`` uses
    ``NullPool``, so every seeding call opens a fresh connection and dials an
    address nobody is listening on — a ``WinError 121`` inside
    ``seed_workspace`` that reads as a database problem and is a DNS one.
    """
    real = socket.getaddrinfo

    def getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        if host == PROVIDER_HOST:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_stub.PUBLIC_ADDRESS, port))]
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


async def _admin(migrate_engine) -> dict[str, str]:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, ADMIN_SESSION)
    return {"cookie": f"prope_session={ADMIN_SESSION}"}


def _provider(completion: dict, models: dict | None = None):  # noqa: ANN202
    return _stub.route(
        models=lambda request: httpx.Response(200, json=models or _stub.model_list()),
        completions=lambda request: httpx.Response(200, json=completion),
    )


async def test_a_provider_that_reports_no_usage_is_refused_and_nothing_is_saved(
    api, migrate_engine, app_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await _admin(migrate_engine)

    with _stub.stub_provider(monkeypatch, _provider(COMPLETION_WITHOUT_USAGE)):
        response = await call(api, "POST", "/api/v1/providers", json_body=BODY, headers=headers)

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.PROVIDER_VERIFICATION_FAILED
    assert response.json()["error"]["details"]["reason"] == "usage_not_reported"

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_CONFIGS) == 0
        assert await db.scalar(COUNT_CREDENTIALS) == 0
        assert await db.scalar(COUNT_EVENTS) == 0


async def test_the_refusal_names_the_missing_usage_object(
    api, migrate_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason is a closed token from `verification`, not the provider's own
    words — an echoing provider must not carry a prompt body out through it."""
    headers = await _admin(migrate_engine)

    with _stub.stub_provider(monkeypatch, _provider(COMPLETION_WITHOUT_USAGE)):
        response = await call(api, "POST", "/api/v1/providers", json_body=BODY, headers=headers)

    detail = response.json()["error"]["details"]["detail"]

    assert "usage object" in detail
    assert "A-030" in detail


async def test_a_provider_that_reports_usage_is_admitted_and_its_catalogue_populates(
    api, migrate_engine, app_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await _admin(migrate_engine)

    with _stub.stub_provider(
        monkeypatch,
        _provider(_stub.completion(), _stub.model_list("gpt-4o-mini", "gpt-4o")),
    ):
        response = await call(api, "POST", "/api/v1/providers", json_body=BODY, headers=headers)

    assert response.status_code == 201, response.body
    body = response.json()

    assert body["verification_status"] == "passed"
    assert body["credential_last_four"] == BODY["credential"][-4:]
    assert "credential" not in body

    models = await call(
        api, "GET", f"/api/v1/providers/{body['provider_config_id']}/models", headers=headers
    )

    assert {entry["model_id"] for entry in models.json()} == {"gpt-4o-mini", "gpt-4o"}

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_EVENTS) == 1


async def test_a_provider_whose_model_list_is_empty_cannot_be_probed_at_all(
    api, migrate_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """There is nothing to complete against, so admission has no evidence — and
    a configuration saved active on no evidence is what A-090 forbids."""
    headers = await _admin(migrate_engine)

    with _stub.stub_provider(
        monkeypatch, _provider(_stub.completion(), {"object": "list", "data": []})
    ):
        response = await call(api, "POST", "/api/v1/providers", json_body=BODY, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason"] == "no_model"


async def test_a_refused_credential_is_reported_as_such_rather_than_as_a_bad_provider(
    api, migrate_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await _admin(migrate_engine)

    with _stub.stub_provider(monkeypatch, _stub.answers(401, {"error": {"message": "no"}})):
        response = await call(api, "POST", "/api/v1/providers", json_body=BODY, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason"] == "credential_rejected"


async def test_an_unverified_configuration_cannot_be_bound_because_it_never_exists(
    api, migrate_engine, app_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3's last clause. There is no half-saved row for a revision to bind:
    the probe runs before the insert, so a failed probe leaves nothing behind."""
    headers = await _admin(migrate_engine)

    with _stub.stub_provider(monkeypatch, _provider(COMPLETION_WITHOUT_USAGE)):
        await call(api, "POST", "/api/v1/providers", json_body=BODY, headers=headers)

    listed = await call(api, "GET", "/api/v1/providers", headers=headers)

    assert listed.json() == []

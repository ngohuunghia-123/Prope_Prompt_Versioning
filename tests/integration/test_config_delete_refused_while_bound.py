"""AC-10 — disable is always available; delete is the foreign key's decision.

The refusal comes from `registry.revision.provider_config_id`, NOT from asking
prompt-registry: that direction is forbidden (module_map.md). The constraint
points the same way the dependency already runs, so it adds no edge — and it
does not exist yet, because prompt-registry is wave 3. What ships here is the
half that is testable today: the disable path, the refusal shape, and the
guarantee that a disabled configuration stays readable while refusing dispatch.

The bound-revision half is recorded as `OQ-140` rather than asserted against a
table nothing has created.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.db.session import workspace_transaction
from prope.errors import ErrorCode, install_error_envelope
from prope.provider_access.api import router as provider_access_router
from prope.provider_access.dispatch import dispatch
from prope.provider_access.domain import DispatchError, ErrorClass, Origin
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.provider_access import (
    CONFIG_ID,
    seed_catalogue_entry,
    seed_credential,
    seed_provider_config,
)
from tests.unit import WORKSPACE_A

ADMIN_SESSION = "ses_provider_delete_000000001"

COUNT_CONFIGS = text("SELECT count(*) FROM provider.provider_config")
COUNT_DISABLE_EVENTS = text(
    "SELECT count(*) FROM history.history_event WHERE action = 'provider_disabled'"
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


async def _configured(migrate_engine) -> dict[str, str]:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, ADMIN_SESSION)
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)
    await seed_catalogue_entry(migrate_engine)
    return {"cookie": f"prope_session={ADMIN_SESSION}"}


async def test_a_configuration_nothing_binds_is_deleted_with_its_event(
    api, migrate_engine, app_sessionmaker
) -> None:
    headers = await _configured(migrate_engine)

    response = await call(api, "DELETE", f"/api/v1/providers/{CONFIG_ID}", headers=headers)

    assert response.status_code == 204, response.body

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_CONFIGS) == 0
        assert await db.scalar(COUNT_DISABLE_EVENTS) == 1


async def test_disabling_leaves_the_configuration_and_its_catalogue_readable(
    api, migrate_engine
) -> None:
    """A-096. A revision bound to a disabled configuration must still explain
    itself: pointing at nothing is what deletion would do."""
    headers = await _configured(migrate_engine)

    disabled = await call(
        api,
        "PATCH",
        f"/api/v1/providers/{CONFIG_ID}",
        json_body={"status": "disabled"},
        headers=headers,
    )

    assert disabled.status_code == 200, disabled.body
    assert disabled.json()["status"] == "disabled"

    readable = await call(api, "GET", f"/api/v1/providers/{CONFIG_ID}", headers=headers)
    catalogue = await call(api, "GET", f"/api/v1/providers/{CONFIG_ID}/models", headers=headers)

    assert readable.status_code == 200
    assert [entry["model_id"] for entry in catalogue.json()] == ["gpt-4o-mini"]


async def test_dispatch_is_refused_for_a_disabled_configuration(
    api, migrate_engine, app_sessionmaker
) -> None:
    headers = await _configured(migrate_engine)
    await call(
        api,
        "PATCH",
        f"/api/v1/providers/{CONFIG_ID}",
        json_body={"status": "disabled"},
        headers=headers,
    )

    result = await dispatch(
        app_sessionmaker,
        workspace_id=WORKSPACE_A,
        provider_config_id=CONFIG_ID,
        upstream_model="gpt-4o-mini",
        parameters={},
        messages=({"role": "user", "content": "hi"},),
    )

    assert isinstance(result, DispatchError)
    assert result.error_class is ErrorClass.CONFIGURATION_UNUSABLE
    assert result.origin is Origin.PROPE
    assert result.fallback_eligible is False


async def test_disabling_writes_both_the_update_and_the_disable_event(
    api, migrate_engine, app_sessionmaker
) -> None:
    """Two facts, recorded separately: what changed, and that it was disabled."""
    headers = await _configured(migrate_engine)

    await call(
        api,
        "PATCH",
        f"/api/v1/providers/{CONFIG_ID}",
        json_body={"status": "disabled"},
        headers=headers,
    )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_DISABLE_EVENTS) == 1
        updated = await db.scalar(
            text("SELECT count(*) FROM history.history_event WHERE action = 'provider_updated'")
        )

    assert updated == 1


async def test_a_second_disable_does_not_write_a_second_disable_event(
    api, migrate_engine, app_sessionmaker
) -> None:
    """A trail that recorded a state change every time somebody re-sent the same
    request would be a trail nobody can read for when access actually ended."""
    headers = await _configured(migrate_engine)

    for _ in range(2):
        await call(
            api,
            "PATCH",
            f"/api/v1/providers/{CONFIG_ID}",
            json_body={"status": "disabled"},
            headers=headers,
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_DISABLE_EVENTS) == 1


async def test_deleting_a_configuration_that_does_not_exist_is_not_found(
    api, migrate_engine
) -> None:
    headers = await _configured(migrate_engine)

    response = await call(
        api, "DELETE", "/api/v1/providers/prv_01J0000000000000000NONE", headers=headers
    )

    assert response.status_code == 404
    assert response.code == ErrorCode.NOT_FOUND


def test_the_refusal_code_for_a_bound_configuration_is_declared() -> None:
    """The shape A-052 uses for retiring a released prompt. It is declared now
    so the wave-3 foreign key has somewhere to land, and so the SPA's catalogue
    can carry the string before the constraint exists (ADR-0053)."""
    assert ErrorCode.PROVIDER_BOUND_BY_REVISIONS == "provider_bound_by_revisions"

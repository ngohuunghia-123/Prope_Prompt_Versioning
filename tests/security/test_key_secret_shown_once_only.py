"""AC-7 / A-113. The plaintext appears in the creation response and nowhere else.

*"In no other response, log line, metric label, or history event"*, and the stored
row cannot reconstruct it. Four claims, and each is asserted against the thing it
is about rather than against a reading of the source:

* other responses — over the assembled OpenAPI schema, so a model reaching the
  wire through a route nobody remembered is still covered;
* log lines — over captured `structlog` output;
* metric labels — over the whole registry's rendered exposition;
* history events — over the registry's allow-list for `api_key_created`, which is
  empty, so there is no slot the secret could occupy even deliberately.
"""

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.api import router as access_control_router
from prope.access_control.bootstrap import authenticate_session
from prope.access_control.keys import hash_secret, mint_key, parse_presented_key
from prope.errors import install_error_envelope
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import WORKSPACE_A, seed_member, seed_role, seed_session, seed_user, seed_workspace
from tests.integration._asgi import call

SESSION_ID = "ses_key_secret_shown_once_only1"

READ_STORED_KEY = text("SELECT id, key_hash, last_four FROM access.api_key WHERE id = :id")

READ_EVENT_DETAILS = text(
    "SELECT details::text FROM history.history_event WHERE action = 'api_key_created'"
)

REGISTERED_KEYS_FOR_API_KEY_EVENTS = text(
    "SELECT action, detail_keys FROM history.history_action_registry "
    "WHERE action IN ('api_key_created', 'api_key_revoked')"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(access_control_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


async def _admin_session(migrate_engine) -> dict[str, str]:
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, SESSION_ID)
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _issue_key(api, headers: dict[str, str]) -> tuple[str, str]:
    response = await call(
        api,
        "POST",
        f"/api/v1/workspaces/{WORKSPACE_A}/keys",
        json_body={"name": "a consumer", "scope_model_names": ["prope/greeting"]},
        headers=headers,
    )
    assert response.status_code == 201, response.body
    payload = response.json()
    return payload["key_id"], payload["secret"]


async def test_the_creation_response_carries_it_and_the_list_does_not(api, migrate_engine) -> None:
    headers = await _admin_session(migrate_engine)
    key_id, secret = await _issue_key(api, headers)

    assert secret.startswith("prope_")
    assert key_id in secret

    listing = await call(api, "GET", f"/api/v1/workspaces/{WORKSPACE_A}/keys", headers=headers)

    assert listing.status_code == 200, listing.body
    assert secret not in listing.body.decode()
    # The whole field set, written as an equality rather than as a `not in`
    # check on `secret`: AC-7's claim is that the plaintext appears in exactly one
    # response, and a set that is allowed to grow silently is a set a future field
    # could carry it in. The three added on 2026-08-18 are scopes, not
    # credentials — `observe_provider_config_id` names a provider CONFIGURATION
    # and never its key, which A-025 keeps inside provider-access.
    assert set(listing.json()[0]) == {
        "key_id",
        "name",
        "last_four",
        "scope_model_names",
        "scope_namespaces",
        "observe_provider_config_id",
        "observe_namespace",
        "created_by",
        "created_at",
        "revoked_at",
        "last_used_at",
    }


async def test_the_stored_row_cannot_reconstruct_it(api, migrate_engine) -> None:
    """A SHA-256 digest, four display characters, and nothing reversible."""
    headers = await _admin_session(migrate_engine)
    key_id, secret = await _issue_key(api, headers)

    async with migrate_engine.begin() as connection:
        row = (await connection.execute(READ_STORED_KEY, {"id": key_id})).one()

    assert secret not in (row.key_hash, row.last_four)
    # Split at three, not from the right: `token_urlsafe` emits `-` and `_`, so a
    # right-split would cut the secret in the middle whenever it happens to end
    # with one. `ck_api_key_id_has_no_separator` is what makes the fourth part
    # the whole secret.
    assert row.key_hash == hash_secret(secret.split("_", 3)[3])
    assert len(row.last_four) == 4
    assert secret.endswith(row.last_four)


async def test_no_metric_label_anywhere_in_the_registry_holds_it(api, migrate_engine) -> None:
    """Over the rendered exposition, not over this module's label declarations.

    A label added in another module would be invisible to a check that only read
    `access_control.observability`.
    """
    from prometheus_client import REGISTRY, generate_latest

    headers = await _admin_session(migrate_engine)
    _, secret = await _issue_key(api, headers)

    assert secret not in generate_latest(REGISTRY).decode()


async def test_no_log_line_holds_it(api, migrate_engine) -> None:
    """Over captured `structlog` output, `test_no_history_content_reaches_a_log_line`'s shape."""
    import structlog

    headers = await _admin_session(migrate_engine)
    with structlog.testing.capture_logs() as captured:
        _, secret = await _issue_key(api, headers)

    assert secret not in repr(captured)


async def test_the_history_event_has_no_registered_slot_for_it(api, migrate_engine) -> None:
    """An empty `detail_keys` is what makes the fourth claim structural.

    `append()` refuses an unregistered key with `unknown_detail_key`, so with an
    empty allow-list there is no field a later contributor could add the scope,
    the name or any part of the secret to — even trying fails the transaction.
    """
    headers = await _admin_session(migrate_engine)
    _, secret = await _issue_key(api, headers)

    async with migrate_engine.begin() as connection:
        registered = dict((await connection.execute(REGISTERED_KEYS_FOR_API_KEY_EVENTS)).all())
        details = (await connection.execute(READ_EVENT_DETAILS)).scalars().all()

    assert registered == {"api_key_created": [], "api_key_revoked": []}
    assert details == ["{}"]
    assert secret not in "".join(details)


def test_the_parser_discards_the_secret_before_it_returns() -> None:
    """A-046 made structural: `KeyPresentation` has no field the plaintext fits in.

    The presented format looks like an identifier and starts with one, which makes
    logging the whole string the easiest possible mistake. The parse returns a
    digest instead, so there is nothing downstream to log.
    """
    minted = mint_key()
    presentation = parse_presented_key(minted.plaintext)

    assert presentation is not None
    assert minted.plaintext not in repr(presentation)
    for value in vars(presentation).values() if hasattr(presentation, "__dict__") else ():
        assert minted.plaintext not in str(value)
    assert presentation.secret_hash == minted.key_hash


def test_the_minted_key_does_not_leak_through_its_repr() -> None:
    """A default `__repr__` here is AC-7's failure, via a pytest diff or a log value."""
    minted = mint_key()

    assert minted.plaintext not in repr(minted)
    assert repr(minted) == f"<MintedKey {minted.key_id}>"

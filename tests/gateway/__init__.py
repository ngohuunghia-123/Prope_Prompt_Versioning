"""Shared factories for the gateway's tests.

Same placement argument as ``tests/access_control/`` and
``tests/prompt_registry/``: a per-subject package named after the module,
created when its subject arrived.

**There is no schema here and there is nothing to seed for this module.** The
gateway owns no table — it is the first module in the build whose factories are
entirely about other modules' rows and about standing its application object up.
What this file supplies is a real consumer key (its plaintext and its stored
hash, from the production minting code rather than from a plausible-looking
string) and the gateway application with a sessionmaker bound the way
``prope.app``'s lifespan binds it.
"""

import socket
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control.keys import PRESENTED_PREFIX, hash_secret
from prope.call_ledger.domain import CallRecordDraft
from prope.call_ledger.enqueue import handoff
from prope.gateway.admission import reset_admission
from prope.gateway.app import create_gateway_app
from prope.gateway.cache import reset_resolution_cache
from tests.access_control import KEY_ID, seed_api_key, seed_member, seed_user, seed_workspace
from tests.prompt_registry import PROMPT_ID, VERSION_ID, approve, release, seed_prompt, seed_revision
from tests.integration._asgi import Response
from tests.provider_access import CONFIG_ID, seed_credential, seed_provider_config
from tests.provider_access._stub import PUBLIC_ADDRESS, Recorder, stub_provider
from tests.unit import WORKSPACE_A

__all__ = [
    "CONFIG_ID",
    "KEY_ID",
    "enqueued_records",
    "resolve_publicly",
    "stub_upstream",
    "stream_call",
    "MODEL",
    "PROMPT_ID",
    "SECOND_KEY_ID",
    "SECRET",
    "UPSTREAM_MODEL",
    "VERSION_ID",
    "WORKSPACE_A",
    "authorization",
    "gateway_api",
    "presented",
    "seed_key",
    "seed_released_world",
]

#: A test-only consumer secret. Constant rather than random so a failure is
#: reproducible, exactly as ``tests/access_control``'s password is.
SECRET = "sk-test-consumer-secret-000000"

SECOND_KEY_ID = "key_01J000000000000000000KEY2"

#: ``tests/prompt_registry``'s prompt, spelled as a model name.
MODEL = "support/refund-classifier"

UPSTREAM_MODEL = "gpt-4o-mini"

#: The host in ``tests/provider_access``' ``BASE_URL``, and the only name
#: :func:`resolve_publicly` answers for.
PROVIDER_HOST = "provider.example"


async def seed_released_world(
    migrate_engine: AsyncEngine,
    *,
    body: str = "You are a helpful assistant.",
    fallback_answer: str | None = None,
    scope: tuple[str, ...] = (MODEL,),
    #: ADR-0061 / A-158. Defaulted empty so every existing caller is unchanged —
    #: which is also the production default, and the reason a folder scope could
    #: be added without touching a single key that already existed.
    scope_namespaces: tuple[str, ...] = (),
) -> None:
    """Everything four other modules must have in place for one gateway call.

    A workspace and a member, because ``access.api_key`` and
    ``registry.prompt_property`` both point at them; a provider configuration
    that has PASSED verification and a real encrypted credential, because
    ``dispatch`` refuses a configuration that has not (A-090) and decrypts
    through the real envelope (ADR-0014); an Approved revision bound to that
    configuration; the released pointer, which BR-03's composite foreign key
    will not accept until the revision is Approved; and the consumer key with
    the model name on its scope.

    That list IS the gateway's dependency graph, and the fact that this factory
    is long while the module owns no table is the shape of a module whose whole
    job is to join four others on a 50 ms path.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)

    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)

    await seed_prompt(migrate_engine)
    await seed_revision(
        migrate_engine,
        body=body,
        provider_config_id=CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
        fallback_answer=fallback_answer,
    )
    await approve(migrate_engine)
    await release(migrate_engine)

    await seed_key(migrate_engine, scope=scope, scope_namespaces=scope_namespaces)


def presented(key_id: str = KEY_ID, secret: str = SECRET) -> str:
    """``prope_<key_id>_<secret>`` — ADR-0021's format, built the way keys.py does."""
    return f"{PRESENTED_PREFIX}_{key_id}_{secret}"


def authorization(key_id: str = KEY_ID, secret: str = SECRET) -> dict[str, str]:
    return {"authorization": f"Bearer {presented(key_id, secret)}"}


async def seed_key(
    migrate_engine: AsyncEngine,
    key_id: str = KEY_ID,
    *,
    secret: str = SECRET,
    scope: tuple[str, ...] = (MODEL,),
    scope_namespaces: tuple[str, ...] = (),
    workspace_id: str = WORKSPACE_A,
    **overrides: object,
) -> str:
    """One consumer key whose stored hash is the real digest of ``secret``.

    ``tests/access_control.seed_api_key`` defaults ``key_hash`` to sixty-four
    zeroes, which is right for a test about the ROW and useless for a test that
    has to authenticate — a presented key is verified against this column in
    constant time, so a placeholder digest is a key nothing can ever present.
    """
    return await seed_api_key(
        migrate_engine,
        key_id,
        key_hash=hash_secret(secret),
        scope_model_names=scope,
        scope_namespaces=scope_namespaces,
        workspace_id=workspace_id,
        **overrides,
    )


def resolve_publicly(monkeypatch) -> None:  # noqa: ANN001
    """Make ``provider.example`` resolve to a public address for this test.

    ADR-0047 refuses loopback, link-local, reserved and private ranges at dispatch
    time, and ``tests/provider_access/_stub`` explains why the stub sits at the
    httpx transport rather than on a socket: a real server on ``127.0.0.1`` is
    precisely what that control exists to refuse, and relaxing the guard "for
    tests" would disable the thing the tests prove.

    So the NAME resolves publicly and no packet is sent — the guard runs for
    real, and ``tests/security/test_base_url_ssrf_guard.py`` is where it is
    pointed at every refused range in turn.

    **Only ``provider.example`` is intercepted, and that is not tidiness.**
    ``socket.getaddrinfo`` is what asyncpg resolves the test container's
    PostgreSQL through as well; a blanket answer sends every database connection
    in the test to a public address and the failure arrives four layers away, as
    a connect timeout inside SQLAlchemy's pool, with nothing naming this
    function.
    """
    real = socket.getaddrinfo

    def getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001, ANN202
        if host != PROVIDER_HOST:
            return real(host, port, *args, **kwargs)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_ADDRESS, port))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@contextmanager
def stub_upstream(monkeypatch, handler) -> Iterator[Recorder]:  # noqa: ANN001
    """One provider, stubbed at the transport, with the SSRF guard left switched on.

    The two halves are always wanted together and separating them at every call
    site is how one of the two gets forgotten — and a forgotten
    :func:`resolve_publicly` fails as ``provider_address_refused``, which reads
    as a gateway bug rather than as a test rig that never left the house.
    """
    resolve_publicly(monkeypatch)
    with stub_provider(monkeypatch, handler) as recorder:
        yield recorder


async def stream_call(
    application,  # noqa: ANN001
    path: str,
    *,
    json_body: object,
    headers: dict[str, str],
) -> Response:
    """One request whose response is a stream, drained to the end.

    **`tests/integration/_asgi.call` cannot do this and it is not a defect
    there.** Its `receive` answers `http.disconnect` once the body is delivered,
    which is exactly right for a request/response route and fatal for a streaming
    one: Starlette's `StreamingResponse` races `stream_response` against
    `listen_for_disconnect`, so a disconnect arriving immediately truncates the
    relay — and the symptom is a body that stops mid-stream with no error, which
    reads as a gateway bug rather than as a test client hanging up.

    So `receive` here delivers the body and then **awaits forever**. The task
    group cancels it when the stream finishes, which is the same shape a real
    client's open connection has. Everything else — building the scope,
    collecting the messages — is `_asgi.call`'s, and this stays a variant of it
    rather than a second ASGI driver.
    """
    import asyncio
    import json

    raw = json.dumps(json_body).encode()
    header_list = [
        (b"host", b"testserver"),
        (b"content-type", b"application/json"),
        (b"content-length", str(len(raw)).encode()),
    ]
    header_list.extend((name.lower().encode(), value.encode()) for name, value in headers.items())

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": header_list,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    messages: list[dict] = []
    delivered = False

    async def receive() -> dict:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send(message: dict) -> None:
        messages.append(message)

    await application(scope, receive, send)

    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return Response(
        status_code=start["status"],
        headers={key.decode(): value.decode() for key, value in start["headers"]},
        body=body,
    )


def enqueued_records() -> list[CallRecordDraft]:
    """Every draft this process handed to call-ledger, read out of the handoff.

    **Read from the buffer rather than from PostgreSQL, and that is the point of
    A-087.** The record is published by a background task and written by the
    worker; a test that asserted against `ledger.call_record` would be asserting
    about call-ledger's drain rather than about what the gateway handed over, and
    it would have to wait for a broker to be running in order to see anything at
    all. `enqueue` never raises and never blocks (INT-018), so what it accepted
    is the whole of this module's obligation.

    Non-destructive: the drafts are read out of the queue's own deque without
    consuming them, so a test may assert twice and `reset_handoff` still owns the
    cleanup.
    """
    return [item.draft for item in handoff()._queue]  # noqa: SLF001


@contextmanager
def gateway_api(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> Iterator[FastAPI]:
    """The gateway application object, standalone, with its sessionmaker bound.

    **A fresh application per test rather than the module-level ``prope.gateway:
    app``.** ADR-0050's whole claim is that this object can be instantiated and
    driven without the management surface, which is what makes the contract test
    exercise what a consumer actually reaches — and a shared instance would carry
    one test's ``app.state`` into the next.

    The two PROCESS-lifetime structures behind it are reset on both sides. The
    resolution cache is a module global with a 30 s TTL, so a binding cached in
    one test is still warm in the next and the release a later test performs
    would appear not to have happened; the admission counter is a module global
    too, and a test that refused at the cap would leave its 20 in flight forever.
    Same argument ``reset_handoff`` and ``clear_credential_cache`` make in
    ``tests/conftest.py``, for the same class of bug.
    """
    reset_resolution_cache()
    reset_admission()
    application = create_gateway_app()
    application.state.sessionmaker = app_sessionmaker
    try:
        yield application
    finally:
        reset_resolution_cache()
        reset_admission()
